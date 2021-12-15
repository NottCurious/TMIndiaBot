import discord


class ViewAdder(discord.ui.View):
    def __init__(self, buttons: list[discord.ui.Button]):
        super().__init__()

        for button in buttons:
            self.add_item(button)
