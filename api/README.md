dev run:
python3 dev.py

prod run (local prod testing):
./start.sh



### Keeping future schedules current

Apply `api/migrations/20261030_game_kickoff_tbd.sql` before deploying the schedule
API. ESPN's `timeValid=false` means kickoff is unannounced. These fixtures use
noon Eastern as a date anchor and return `timeTBD=true`; all schedule views show
`TBD` rather than presenting that anchor as kickoff. Confirmed late games retain
their actual timestamps.

Run `python3 api/cronJobs/cronRefreshSchedules.py` daily alongside live scoreboard
polling. It refreshes the next 21 days once per sport season, including moved
games and newly announced kickoff times. For a full future football repair use
`--sport-season-id ID --days 100`. Refresh after deploying both API and frontend
so existing placeholders acquire the flag and correct calendar date.
