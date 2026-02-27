import sys

if len(sys.argv) > 1 and sys.argv[1] == "bot":
    from agent.interfaces.telegram import run_bot

    run_bot()
else:
    from agent.interfaces.cli import main

    main()
