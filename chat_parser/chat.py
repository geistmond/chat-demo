# Class definitions for parsing chats.

# Regular expression handling
import re

# Type consistency
from typing import Tuple, List


class Parser():
    logs = ""

    def __init__(self, logs):
        self.logs = logs

    def get_timestamps(self) -> List[List[str]]:
        """Return a list of lists with timestamp strings and remainder strings.

        Args:
            log (str): IRC chatlogs

        Returns:
            List[List[str]]: list of lists of this format
                [["2024-06-02 21:46:57.519505", "@user1 said blah"], 
                ["2024-06-02 21:48:01.111222", "@user2 said wut"]]
        """
        # First separate by lines
        l = self.logs
        lines = l.split("\n")

        # Example IRC timestamp including brackets [2024-06-02 21:46:57.519505]
        # You can truncate the decimals to leave off microseconds: [2024-06-02 21:46:57]
        timestamp_re = r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d{6})\]"

        pattern = re.compile(timestamp_re)
        pattern.findall(log)

        return [pattern.split(l)[1:] for l in lines]

    # Extract users as second element ['"", "@user", ""]
    def get_users(self) -> List[List[str]]:
        l = self.logs
        lines = l.split("\n")
        user_re = r"\<[a-zA-Z0-9_]+\>"
        pattern = re.compile(user_re)
        return [[pattern.findall(l), pattern.split(l)[1:]] for l in lines]

    # Extract commands
    def get_commands(self) -> List[List[str]]:
        l = self.logs
        lines = l.split("\n")
        valid_commands = ["/set", "/unset", "/mute",
                          "/ban", "/unban", "/suspend", "/set"]
        command_re = "/[a-zA-Z0-9_]+"
        pattern = re.compile(command_re)
        command_attempts = pattern.findall(log)
        if False in [c in valid_commands for c in command_attempts]:
            print("Alert: Invalid commands given.")
        return [pattern.split(l) for l in lines]


# Example that extracts users from this random example from bash-org-archive.com where the old bash.org now lives
# This lacks the timestamps that would be from, perhaps, 1998.
sample = """<Cthon98> hey, if you type in your pw, it will show as stars
<Cthon98> ********* see!
<AzureDiamond> hunter2
<AzureDiamond> doesnt look like stars to me
<Cthon98> <AzureDiamond> *******
<Cthon98> thats what I see
<AzureDiamond> oh, really?
<Cthon98> Absolutely
<AzureDiamond> you can go hunter2 my hunter2-ing hunter2
<AzureDiamond> haha, does that look funny to you?
<Cthon98> lol, yes. See, when YOU type hunter2, it shows to us as *******
<AzureDiamond> thats neat, I didnt know IRC did that
<Cthon98> yep, no matter how many times you type hunter2, it will show to us as *******
<AzureDiamond> awesome!
<AzureDiamond> wait, how do you know my pw?
<Cthon98> er, I just copy pasted YOUR ******'s and it appears to YOU as hunter2 cause its your pw
<AzureDiamond> oh, ok."""

p = Parser(sample)
users = p.get_users()
print(users)
