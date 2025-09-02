
# Workflow
* The bot should be triggered by a homeassistant automation, which will trigger when I'm in the office. You don't need to write the homeassistant automation.
* When triggered, the bot should message me for confirmation that I'll be sleeping at my friends that night. I will confirm by reacting to the message with a number of the emoji in the next bullet point, followed by a thumbs up.
* It should then message our group conversation with a message along the following lines: "Alex is here! React with <> if you'd like to go for lunch at 12:30, <> if you'd like Alex to bring back a picnic dinner, <> if you'd like to go to the pub for dinner, <> if you're up for an evening walk, or <> if you'd like an evening cycle, or <> if you'd like other fun. <> Represents an appropriate emoji. The options included should be trigggered by my reactions.
* It should then message me to remind me to go to lunch if appropriate, and just before I leave work to say what I need to buy for the evening.

# Implmentation Detail
* Matrix ( https://matrix.org/ ) bot.
* Is a maubot ( https://github.com/maubot/maubot ) plugin.
* Docs for creating maubot plugins are here: https://docs.mau.fi/maubot/dev/getting-started.html
