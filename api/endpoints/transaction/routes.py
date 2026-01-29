from endpoints.transaction.transactionEndpoints import TransactionEndpoints

def setup_routes(app, engine):

    transactionEndpoints = TransactionEndpoints(engine)

    # Propose a trade (creates Transaction row with PROPOSED)
    app.add_url_rule(
        "/api/league/<int:league_id>/week/<int:week_id>/trade/propose",
        view_func=transactionEndpoints.propose_trade,
        methods=["POST"],
    )

    # Accept/Reject a proposed trade
    app.add_url_rule(
        "/api/league/<int:league_id>/transaction/<int:transaction_id>/trade/respond",
        view_func=transactionEndpoints.respond_trade,
        methods=["POST"],
    )

    # Cancel your own proposed trade
    app.add_url_rule(
        "/api/league/<int:league_id>/transaction/<int:transaction_id>/trade/cancel",
        view_func=transactionEndpoints.cancel_trade,
        methods=["POST"],
    )

    # New: free agency add/drop
    app.add_url_rule(
        "/api/league/<int:leagueId>/freeAgency/addDrop",
        view_func=transactionEndpoints.free_agency_add_drop,
        methods=["POST"],
    )

    app.add_url_rule(
        "/api/league/<int:league_id>/transactions/trades/open",
        view_func=transactionEndpoints.get_open_trade_transactions,
        methods=["POST"],
    )

    app.add_url_rule(
        "/api/league/<int:league_id>/transaction/<int:transaction_id>/trade/veto",
        view_func=transactionEndpoints.veto_trade,
        methods=["POST"],
    )

    app.add_url_rule(
        "/api/league/<int:league_id>/transaction/<int:transaction_id>/trade/apply",
        view_func=transactionEndpoints.apply_trade,
        methods=["POST"],
    )

    app.add_url_rule(
        "/api/league/<int:league_id>/transaction/pending",
        view_func=transactionEndpoints.get_transactions_for_league,
        methods=["GET"],
    )
