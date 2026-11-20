import sys


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if "--self-test" in argv[1:]:
        from tunnelflare_gui.selftest import run_self_test
        return run_self_test(argv[1:])
    if argv[1:2] == ["--update"]:
        from tunnelflare_backend.updater import run_cli
        return run_cli(argv[2:])

    import signal
    from tunnelflare_gui.application import create_application
    from tunnelflare_gui.main_window import MainWindow
    from tunnelflare_gui.single_instance import listen_for_activation, notify_running_instance

    app = create_application(argv)
    if notify_running_instance():
        return 0  # TunnelFlare is already running and now shows its window
    window = MainWindow()
    listen_for_activation(window.show_window, window)
    window.show()

    # Handle Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
