from launchpad.app import LaunchPadApp
from launchpad.branding import window_title


def main() -> None:
    app = LaunchPadApp()
    app.title(window_title(app.db))
    app.mainloop()


if __name__ == "__main__":
    main()
