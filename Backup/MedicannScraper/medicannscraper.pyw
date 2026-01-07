from __future__ import annotations

import sys

# Entry selector: default to FlowerTracker UI, parser launched with --parser
if __name__ == "__main__":
    if "--parser" in sys.argv:
        from ui_main import App

        app = App()
        app.mainloop()
    else:
        import flowertracker

        flowertracker.main()
