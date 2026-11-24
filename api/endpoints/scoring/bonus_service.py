"""Season bonus orchestration from current ownership and validated facts."""
import json
from .bonus_repository import SeasonBonusRepository
from .rules import conference_placement_bonus, national_playoff_bonus
from rules.nationalBonusIdentity import FINAL_ROUNDS
from rules.playoffCoverage import bracket_complete


class SeasonBonusService:
    def __init__(self, repository=None):
        self.repository = repository or SeasonBonusRepository()

    def compute(self, conn, league_id, member_ids, config):
        points = {mid:0.0 for mid in member_ids}
        status = {'state':'ready','components':{},'snapshotIds':[]}
        context = self.repository.context(conn,league_id)
        if not context or context['weekNumber'] is None:
            return {'points':points,'status':{**status,'state':'pending','components':{'roster':'pending'}}}
        owned = {mid:[] for mid in member_ids}
        roster = self.repository.roster(conn,league_id,context['weekNumber'])
        for team in roster:
            if team['memberId'] in owned:
                owned[team['memberId']].append(team['sportTeamId'])
        if any(key in config for key in ('conferenceChampion','conferenceBottom')):
            snapshots = self.repository.snapshots(conn,context['sportSeasonId'])
            placements = {}
            for snapshot in snapshots:
                entries = snapshot['entries']
                if isinstance(entries,str): entries=json.loads(entries)
                for entry in entries:
                    placements[(snapshot['sportConferenceId'],entry['sportTeamId'])]=entry
            valid = {team['sportTeamId']:placements[(team['sportConferenceId'],team['sportTeamId'])]
                     for team in roster if (team['sportConferenceId'],team['sportTeamId']) in placements}
            complete = all(team['sportConferenceId'] is not None and team['sportTeamId'] in valid for team in roster)
            status['snapshotIds'] = sorted(s['id'] for s in snapshots if any(t['sportConferenceId']==s['sportConferenceId'] for t in roster))
            for key in ('conferenceChampion','conferenceBottom'):
                if key not in config: continue
                status['components'][key]='ready' if complete else 'pending'
                contribution=conference_placement_bonus(valid,owned,config[key] or {},bottom=key=='conferenceBottom')
                for mid in member_ids: points[mid]+=contribution[mid]
        if 'farthestInPlayoffs' in config or 'playoffDepth' in config:
            self._playoffs(conn,context,member_ids,owned,config,points,status)
        if 'pending' in status['components'].values(): status['state']='pending'
        return {'points':points,'status':status}

    def _playoffs(self,conn,context,member_ids,owned,config,points,status):
        canonical = config.get('farthestInPlayoffs')
        award = float((canonical or {}).get('farthest',0)) if canonical is not None else float((config.get('playoffDepth') or {}).get('first',0))
        tournaments = self.repository.tournaments(conn,context['sportSeasonId'])
        depths_by_tournament = {}
        subdivision=context.get('subdivision')
        if subdivision in ('FBS','FCS'):
            tournaments=[t for t in tournaments if t['code']==subdivision+'_PLAYOFFS']
        pending = not bool(tournaments)
        codes=[t['code'] for t in tournaments]
        for tournament in tournaments:
            code = tournament['code']
            if code not in FINAL_ROUNDS: continue
            if codes.count(code)!=1:
                pending=True
                continue
            subdivision = context.get('subdivision')
            if subdivision in ('FBS','FCS') and code != subdivision+'_PLAYOFFS': continue
            games = self.repository.playoff_games(conn,context['sportSeasonId'],tournament['id'])
            valid = bool(games) and tournament['ended']
            depths = {mid:0 for mid in member_ids}
            team_depth = {}
            final_count = 0
            for game in games:
                rnd = game.get('roundOrder')
                if (not game.get('isCompleted') or game.get('bonusTournamentCode') != code
                        or not isinstance(rnd,int) or not 1<=rnd<=FINAL_ROUNDS[code]
                        or game.get('homeTeamId') is None or game.get('awayTeamId') is None
                        or game['homeScore']==game['awayScore']):
                    valid = False
                    continue
                if rnd==FINAL_ROUNDS[code]: final_count+=1
                for field,won in (('homeTeamId',game['homeScore']>game['awayScore']),('awayTeamId',game['awayScore']>game['homeScore'])):
                    team=game[field]
                    team_depth[team]=max(team_depth.get(team,0),rnd+int(won))
            if not valid or final_count!=1 or not bracket_complete(games,tournament.get('expectedRoundCounts')):
                pending=True
                continue
            for mid in member_ids:
                depths[mid]=max((team_depth.get(team,0) for team in owned[mid]),default=0)
            depths_by_tournament[code]=depths
        contribution=national_playoff_bonus(depths_by_tournament,member_ids,award)
        for mid in member_ids: points[mid]+=contribution[mid]
        status['components']['farthestInPlayoffs']='pending' if pending else 'ready'
