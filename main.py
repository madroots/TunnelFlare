import sys


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if "--self-test" in argv[1:]:
        from tunnelflare_gui.selftest import run_self_test
        return run_self_test(argv[1:])

    import signal
    from tunnelflare_gui.application import create_application
    from tunnelflare_gui.main_window import MainWindow

    app = create_application(argv)
    window = MainWindow()
    window.show()

    # Handle Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
