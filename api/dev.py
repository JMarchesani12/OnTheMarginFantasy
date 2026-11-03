"""Development web entry point: python3 dev.py (from api)."""
from runtime import create_web_app


def main():
    app = create_web_app(use_reloader=True)
    from socketioInstance import socketio
    socketio.run(app, host='0.0.0.0', port=5050, debug=True)


if __name__ == '__main__':
    main()
