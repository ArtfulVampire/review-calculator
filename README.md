# review-calculator
A telegram bot to notify people on their GitHub review requests and something more.
Still has some bindings to the proprietary corporate API for some special fuctionality.
I've implemented it in my free time, it was not my obligation or a duty for the company I've been working for that time.

QuickStart: TODO
check all the URLs and global variables throughout the code
start a local SQL database (e.g. postgresql), apply schema.sql
get a personal GitHub token with an access to your interesting repositories
create a telegram bot and get its token
elaborate your way to deliver all the credentials to the service in secrets.py
run test.py, debug and fix the problems until convergence :-)
run the service (main.py) in a way you like (supervisor, just a backround process, etc)

Requirements: TODO
workaround - try to run test.py and pip install what it is asking for
vault_client is proprietary, 

General structure:
main.py initializes some "crontasks" and "periodic tasks"
each task calls a method from the loop_* file, which does its job and either sends some telegram messages or updates some data in the database
callbacks.py contains the actions for the buttons/choices of the bot menu
the bot menu is drawn using telegram API and implemented in ask_* methods of telegram.py
schema.sql is not really used but provides an overview of what is expected to be in the database

APIs:
Interactions with GitHub are made via graphql API (though it is recommended to use webhooks but it requires to rewrite much)
Interactions with Telegram are made via "long polling" methods
nda.ya.ru is a proprietary link shortener service

The project is quite stale and there are already many more useful alternatives
