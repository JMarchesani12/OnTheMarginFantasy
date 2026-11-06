"""Development web entry point: python3 dev.py (from api)."""


def main():
    # Match production patch ordering before importing runtime/application modules.
    import eventlet
    eventlet.monkey_patch()
    from runtime import create_web_app
    app = create_web_app(use_reloader=True)
    from socketioInstance import socketio
    try:
        socketio.run(app, host='0.0.0.0', port=5050, debug=True)
    finally:
        from runtime import stop_web_listener
        stop_web_listener(app)


if __name__ == '__main__':
    main()
