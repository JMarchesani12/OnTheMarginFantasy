from typing import Any, Dict
from venv import logger
from flask import request, jsonify
from .leagueModel import LeagueModel
from .admission_service import AdmissionService
from .member_service import MemberService
from .league_admin_service import LeagueAdminService
from .contracts import AdmissionDenied, AdmissionRejected
from actors import UserActor
from authenticatedPrincipal import PrincipalResolutionError, resolve_authenticated_principal

class LeagueEndpoints:
    def __init__(self, db_engine):
        self.leagueModel = LeagueModel(db_engine)
        self.db_engine = db_engine
        self.admission_service = AdmissionService(db_engine)
        self.member_service = MemberService(db_engine)
        self.league_admin_service = LeagueAdminService(db_engine)

    def get_league(self, league_id):
        return self._league_read_response(league_id, 'details')

    def get_league_rules(self, league_id):
        return self._league_read_response(league_id, 'rules')

    def _league_read_response(self, league_id: int, view: str):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            access = self.leagueModel.get_league_read_access(league_id, principal.user_id)
            if not access or (not access['fullAccess'] and not access['isDiscoverable']):
                return jsonify({'message': 'League not found'}), 404
            full_access = bool(access['fullAccess'])
            if not full_access and request.args.get('view') == 'full':
                return jsonify({'message': 'League membership required'}), 403
            if view == 'details' and (not full_access or request.args.get('view') == 'preview'):
                # Recheck metadata entitlement instead of loading a full league row.
                preview = self.leagueModel.get_league_read_access(league_id, principal.user_id)
                if not preview or (not preview['fullAccess'] and not preview['isDiscoverable']):
                    return jsonify({'message': 'League not found'}), 404
                payload = {key: preview[key] for key in ('id', 'name', 'sport', 'commissionerDisplayName')}
            elif view == 'members' and (not full_access or request.args.get('view') == 'preview'):
                payload = self.leagueModel.get_member_previews_for_user(league_id, principal.user_id)
            elif not full_access:
                return jsonify({'message': 'League membership required'}), 403
            else:
                reader = {'reader_user_id': principal.user_id}
                if view == 'details':
                    payload = self.leagueModel.get_league(league_id, **reader)
                elif view == 'rules':
                    payload = self.leagueModel.get_league_rules(league_id, **reader)
                elif view == 'members':
                    payload = self.leagueModel.get_members_for_league(league_id, **reader)
                else:
                    payload = self.leagueModel.get_league_conferences(league_id, **reader)
            if payload is None:
                return jsonify({'message': 'League not found'}), 404
            return jsonify(payload), 200
        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except ValueError as exc:
            return jsonify({'message': str(exc)}), 400
        except Exception:
            return jsonify({'message': 'Failed to read league'}), 500

    def create_league(self):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify({"message": "Expected a JSON object"}), 400

            required = ["name", "teamName", "sport", "numPlayers", "status", "settings", "draftDate", "commissioner", "seasonYear", "isDiscoverable"]
            missing = [field for field in required if field not in data]
            if missing:
                return jsonify({"message": f"Missing fields: {', '.join(missing)}"}), 400

            # Legacy commissioner is an assertion; verified identity owns creation.
            commissioner = data['commissioner']
            if isinstance(commissioner, bool) or not isinstance(commissioner, (int, str)):
                return jsonify({"message": "Invalid commissioner"}), 400
            try:
                requested_commissioner = int(commissioner)
            except ValueError:
                return jsonify({"message": "Invalid commissioner"}), 400
            if requested_commissioner != principal.user_id:
                return jsonify({"error": "commissioner_identity_mismatch"}), 403

            league_data = {
                "name": data["name"],
                "teamName": data["teamName"],
                "sport": data["sport"],
                "numPlayers": data["numPlayers"],
                "status": data["status"],
                "settings": data["settings"],
                "draftDate": data["draftDate"],
                "commissioner": principal.user_id,
                "seasonYear": data["seasonYear"],
                "isDiscoverable": data["isDiscoverable"]
            }
            created = self.league_admin_service.create(
                UserActor(principal.user_id, principal.subject), league_data,
                self.leagueModel.scheduleModel.ensure_weeks_for_league,
            )
            return jsonify(created), 201
        except PrincipalResolutionError as exc:
            return jsonify({"error": exc.code}), exc.status_code
        except ValueError as exc:
            return jsonify({'message': str(exc)}), 400
        except Exception:
            return jsonify({"message": "Failed to create league"}), 500

    def update_league(self, league_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            patch = request.get_json(silent=True)
            if not isinstance(patch, dict):
                return jsonify({"message": "Expected a JSON object"}), 400
            updated = self.league_admin_service.update(
                UserActor(principal.user_id, principal.subject), league_id=league_id, patch=patch,
            )
            return jsonify(updated), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except PermissionError as e:
            return jsonify({"message": str(e)}), 403
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to update league"}), 500

    # POST /api/league/byUser -- userId is a compatibility assertion, not identity.
    def get_leagues_by_user(self):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify({"message": "Expected a JSON object"}), 400
            user_id = data.get('userId')
            if user_id is None:
                return jsonify({"message": "userId is required"}), 400
            if isinstance(user_id, bool) or not isinstance(user_id, (int, str)):
                return jsonify({"message": "Invalid userId"}), 400
            try:
                requested_user_id = int(user_id)
            except ValueError:
                return jsonify({"message": "Invalid userId"}), 400
            if requested_user_id != principal.user_id:
                return jsonify({"error": "user_identity_mismatch"}), 403
            stage = data.get('stage', 'all')
            if stage is not None and not isinstance(stage, str):
                return jsonify({"message": "Invalid stage"}), 400
            leagues = self.leagueModel.get_leagues_for_user(principal.user_id, stage=stage)
            return jsonify(leagues), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except Exception:
            return jsonify({"message": "Failed to fetch leagues"}), 500

    def get_league_members(self, league_id):
        return self._league_read_response(league_id, 'members')

    def get_league_conferences(self, league_id: int):
        return self._league_read_response(league_id, 'conferences')

    def join_request(self, league_id: int):
        """Create own pending request; body userId is a compatibility assertion."""
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({"message": "Expected a JSON object"}), 400
            user_id = body.get('userId')
            if user_id is None:
                return jsonify({"message": "Missing userId"}), 400
            if isinstance(user_id, bool) or not isinstance(user_id, (int, str)):
                return jsonify({"message": "Invalid userId"}), 400
            try:
                requested_user_id = int(user_id)
            except ValueError:
                return jsonify({"message": "Invalid userId"}), 400
            if requested_user_id != principal.user_id:
                return jsonify({"error": "user_identity_mismatch"}), 403

            created = self.admission_service.create_request(
                UserActor(principal.user_id, principal.subject), league_id=league_id,
                message=body.get('message'), team_name=body.get('teamName'),
            )
            return jsonify(created), 201
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except (ValueError, AdmissionRejected) as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            logger.exception("Failed to create join request")
            return jsonify({"message": "Failed to create join request"}), 500

    def join_requests(self, league_id: int):
        """Commissioner-only listing; legacy actingUserId must match principal."""
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({"message": "Expected a JSON object"}), 400
            acting_user_id = body.get('actingUserId')
            if acting_user_id is None:
                return jsonify({"message": "Missing actingUserId"}), 400
            if isinstance(acting_user_id, bool) or not isinstance(acting_user_id, (int, str)):
                return jsonify({"message": "Invalid actingUserId"}), 400
            try:
                requested_actor = int(acting_user_id)
            except ValueError:
                return jsonify({"message": "Invalid actingUserId"}), 400
            if requested_actor != principal.user_id:
                return jsonify({"error": "actor_identity_mismatch"}), 403
            status = body.get('status')
            if status is not None and not isinstance(status, str):
                return jsonify({"message": "Invalid status"}), 400

            rows = self.admission_service.list_requests(
                UserActor(principal.user_id, principal.subject), league_id=league_id, status=status,
            )
            return jsonify(rows), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except (PermissionError, AdmissionDenied) as e:
            return jsonify({"message": str(e)}), 403
        except (ValueError, AdmissionRejected) as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            logger.exception("Failed to list join requests")
            return jsonify({"message": "Failed to list join requests"}), 500

    def add_user_to_league(self, league_id: int, request_id: int):
        """Approve URL-scoped request as verified commissioner."""
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({"message": "Expected a JSON object"}), 400
            acting_user_id = body.get('actingUserId')
            if acting_user_id is None:
                return jsonify({"message": "Missing actingUserId"}), 400
            if isinstance(acting_user_id, bool) or not isinstance(acting_user_id, (int, str)):
                return jsonify({"message": "Invalid actingUserId"}), 400
            try:
                requested_actor = int(acting_user_id)
            except ValueError:
                return jsonify({"message": "Invalid actingUserId"}), 400
            if requested_actor != principal.user_id:
                return jsonify({"error": "actor_identity_mismatch"}), 403

            result = self.admission_service.approve_request(
                UserActor(principal.user_id, principal.subject),
                league_id=league_id, request_id=request_id,
            )
            return jsonify(result), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except (PermissionError, AdmissionDenied) as e:
            return jsonify({"message": str(e)}), 403
        except (ValueError, AdmissionRejected) as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            logger.exception("Failed to approve join request")
            return jsonify({"message": "Failed to approve join request"}), 500

    def deny_join(self, league_id: int, request_id: int):
        """Deny URL-scoped pending request as verified commissioner."""
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({"message": "Expected a JSON object"}), 400
            acting_user_id = body.get('actingUserId')
            if acting_user_id is None:
                return jsonify({"message": "Missing actingUserId"}), 400
            if isinstance(acting_user_id, bool) or not isinstance(acting_user_id, (int, str)):
                return jsonify({"message": "Invalid actingUserId"}), 400
            try:
                requested_actor = int(acting_user_id)
            except ValueError:
                return jsonify({"message": "Invalid actingUserId"}), 400
            if requested_actor != principal.user_id:
                return jsonify({"error": "actor_identity_mismatch"}), 403

            updated = self.admission_service.deny_request(
                UserActor(principal.user_id, principal.subject), league_id=league_id, request_id=request_id,
            )
            return jsonify(updated), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except (PermissionError, AdmissionDenied) as e:
            return jsonify({"message": str(e)}), 403
        except (ValueError, AdmissionRejected) as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            logger.exception("Failed to deny join request")
            return jsonify({"message": "Failed to deny join request"}), 500

    def cancel_join(self, league_id: int, request_id: int):
        """Cancel own URL-scoped pending request as the verified principal."""
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({"message": "Expected a JSON object"}), 400
            user_id = body.get('userId')
            if user_id is None:
                return jsonify({"message": "Missing userId"}), 400
            if isinstance(user_id, bool) or not isinstance(user_id, (int, str)):
                return jsonify({"message": "Invalid userId"}), 400
            try:
                requested_user_id = int(user_id)
            except ValueError:
                return jsonify({"message": "Invalid userId"}), 400
            if requested_user_id != principal.user_id:
                return jsonify({"error": "user_identity_mismatch"}), 403

            updated = self.admission_service.cancel_request(
                UserActor(principal.user_id, principal.subject), league_id=league_id, request_id=request_id,
            )
            return jsonify(updated), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except (PermissionError, AdmissionDenied) as e:
            return jsonify({"message": str(e)}), 403
        except (ValueError, AdmissionRejected) as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            logger.exception("Failed to cancel join request")
            return jsonify({"message": "Failed to cancel join request"}), 500

    # DELETE /api/league/<league_id>/members/<member_id>
    def remove_member(self, league_id: int, member_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({"message": "Expected a JSON object"}), 400
            acting_user_id = body.get('actingUserId')
            if acting_user_id is None:
                return jsonify({"message": "actingUserId is required"}), 400
            if isinstance(acting_user_id, bool) or not isinstance(acting_user_id, (int, str)):
                return jsonify({"message": "Invalid actingUserId"}), 400
            try:
                requested_actor = int(acting_user_id)
            except ValueError:
                return jsonify({"message": "Invalid actingUserId"}), 400
            if requested_actor != principal.user_id:
                return jsonify({"error": "actor_identity_mismatch"}), 403
            shift = body.get('shiftDraftOrder', True)
            if not isinstance(shift, bool):
                return jsonify({"message": "shiftDraftOrder must be a boolean"}), 400

            result = self.member_service.remove(
                UserActor(principal.user_id, principal.subject),
                league_id=league_id, member_id=member_id, shift_draft_order=shift,
            )
            return jsonify(result), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except PermissionError as e:
            return jsonify({"message": str(e)}), 403
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to remove member"}), 500

    def search_leagues(self):
        try:
            q = request.args.get("q", "")
            sport_id = request.args.get("sportId")

            limit = int(request.args.get("limit", 20))
            offset = int(request.args.get("offset", 0))

            results = self.leagueModel.search_leagues(
                q=q,
                sport_id=int(sport_id) if sport_id is not None else None,
                limit=limit,
                offset=offset,
            )
            return jsonify(results), 200

        except ValueError:
            return jsonify({"message": "Invalid parameters"}), 400
        except Exception:
            logger.exception("Failed to search leagues")
            return jsonify({"message": "Failed to search leagues"}), 500

    # DELETE /api/league/<league_id>
    def delete_league(self, league_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({"message": "Expected a JSON object"}), 400
            acting_user_id = body.get('actingUserId')
            if acting_user_id is None:
                return jsonify({"message": "actingUserId is required"}), 400
            if isinstance(acting_user_id, bool) or not isinstance(acting_user_id, (int, str)):
                return jsonify({"message": "Invalid actingUserId"}), 400
            try:
                requested_actor = int(acting_user_id)
            except ValueError:
                return jsonify({"message": "Invalid actingUserId"}), 400
            if requested_actor != principal.user_id:
                return jsonify({"error": "actor_identity_mismatch"}), 403

            result = self.league_admin_service.delete(
                UserActor(principal.user_id, principal.subject), league_id=league_id,
            )
            return jsonify(result), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except PermissionError as e:
            return jsonify({"message": str(e)}), 403
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to delete league"}), 500

    # PATCH /api/league/leagueMember/<member_id>
    def patch_league_member(self, member_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({"message": "Expected a JSON object"}), 400
            if set(body) - {'teamName'}:
                return jsonify({"message": "Only teamName may be updated"}), 400
            team_name = body.get('teamName')
            if not isinstance(team_name, str) or not team_name.strip():
                return jsonify({"message": "Team name is required"}), 400
            updated = self.member_service.rename(
                UserActor(principal.user_id, principal.subject), member_id, team_name,
            )
            return jsonify(updated), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except LookupError:
            return jsonify({"message": "LeagueMember not found"}), 404
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to update league member"}), 500