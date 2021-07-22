import discord
import discord_slash.model
from discord.ext import commands

import asyncio
from typing import List, Optional, Union

from discord_slash.model import ButtonStyle
from discord_slash.context import ComponentContext
from discord_slash.utils.manage_components import create_actionrow, create_button, wait_for_component

from .errors import MissingAttributeException, InvaildArgumentException

EmojiType = List[Union[discord.Emoji, discord.Reaction, discord.PartialEmoji, str]]


class Paginator:
    def __init__(
            self,
            bot: Union[
                discord.Client,
                discord.AutoShardedClient,
                commands.Bot,
                commands.AutoShardedBot,
            ],
            ctx: Union[commands.Context, discord_slash.SlashContext],
            contents: Optional[List[str]] = None,
            embeds: Optional[List[discord.Embed]] = None,
            header: str = '',
            timeout: int = 30,
            use_extend: bool = False,
            only: Optional[discord.User] = None,
            basic_buttons: Optional[EmojiType] = None,
            extended_buttons: Optional[EmojiType] = None,
            left_button_style: Union[int, ButtonStyle] = ButtonStyle.green,
            right_button_style: Union[int, ButtonStyle] = ButtonStyle.green,
            delete_after_timeout: bool = False,
    ) -> None:
        """

        :param bot: The client or bot used to start the paginator.
        Must also have the :class:`discord_slash.SlashCommand` hooks applied
        :param ctx: The context used to invoke the command
        :param contents: The list of messages to go on each page
        :param embeds: The list of embeds to go on each page
        :param header: A message to display at the top of each page
        :param timeout: The amount of time to wait before the check fails
        :param use_extend: Whether to add buttons to go to the first and last page
        :param only: The only :class:`~discord.User` who can use the paginator
        :param basic_buttons: A list of two valid button emojis for the left and right buttons
        :param extended_buttons: A list of two valid button emojis for the first and last buttons
        :param left_button_style: The style to use for the left button
        :param right_button_style: The style to use for the left button
        :param delete_after_timeout: Whether to delete the message after the first sent timeout
        """
        self.bot = bot
        self.context = ctx
        self.contents = contents
        self.embeds = embeds
        self.header = header
        self.timeout = timeout
        self.use_extend = use_extend
        self.only = only
        self.basic_buttons = basic_buttons or ["⬅", "➡"]
        self.extended_buttons = extended_buttons or ["⏪", "⏩"]
        self.left_button_style: int = left_button_style
        self.right_button_style: int = right_button_style
        self.delete_after_timeout = delete_after_timeout
        self.page = 1
        self._left_button = self.basic_buttons[0]
        self._right_button = self.basic_buttons[1]
        self._left2_button = self.extended_buttons[0]
        self._right2_button = self.extended_buttons[1]
        self._message: Optional[discord_slash.model.SlashMessage] = None

        if not issubclass(type(bot),
                          (discord.Client, discord.AutoShardedClient, commands.Bot, commands.AutoShardedBot)):
            raise TypeError(
                "This is not a discord.py related bot class.(only <discord.Client, <discord.AutoShardedClient>, "
                "<discord.ext.commands.Bot>, <discord.ext.commands.AutoShardedBot>) "
            )

        if contents is None and embeds is None:
            raise MissingAttributeException("Both contents and embeds are None.")

        # force contents and embeds to be equal lengths
        if contents is not None and embeds is not None:
            if len(contents) != len(embeds):
                raise InvaildArgumentException(
                    "contents and embeds must be the same length if both are specified"
                )
        else:
            if contents is not None:
                self.embeds = [None]*len(contents)
            elif embeds is not None:
                self.contents = ['']*len(embeds)

        if not isinstance(timeout, int):
            raise TypeError("timeout must be int.")

        if len(self.basic_buttons) != 2:
            raise InvaildArgumentException(
                "There should be 2 elements in basic_buttons."
            )
        if extended_buttons is not None:
            if len(self.extended_buttons) != 2:
                raise InvaildArgumentException(
                    "There should be 2 elements in extended_buttons"
                )

        if left_button_style == ButtonStyle.URL or right_button_style == ButtonStyle.URL:
            raise TypeError(
                "Can't use <discord_component.ButtonStyle.URL> type for button style."
            )

    def button_check(self, ctx: ComponentContext) -> bool:
        """Return False if the message received isn't the proper message,
        or if `self.only` is True and the user isn't the command author"""
        if ctx.origin_message_id != self._message.id:
            return False

        if self.only is not None:
            if ctx.author_id != self.only.id:
                asyncio.get_running_loop().create_task(ctx.send(
                    f'{ctx.author.mention}, you\'re not the author!', hidden=True)
                )
                return False

        return True

    async def start(self) -> None:
        """Start the paginator.
        This method will only return if a timeout occurs and `delete_after_timeout` was set to True"""
        self._message = await self.context.send(
            content=(self.header + '\n' + self.contents[self.page - 1]) or None,
            embed=self.embeds[self.page - 1],
            components=(await self._make_buttons()))
        while True:
            try:
                ctx = await wait_for_component(self.bot, check=self.button_check, messages=self._message)

                if ctx.custom_id == "_extend_left_click":
                    self.page = 1
                elif ctx.custom_id == "_left_click":
                    self.page = (self.page - 1 or 1)  # Don't go back too far
                elif ctx.custom_id == "_right_click":
                    self.page += (self.page != len(self.embeds))  # Adding bools ~= adding numbers
                elif ctx.custom_id == "_extend_right_click":
                    self.page = len(self.embeds)

                await ctx.edit_origin(content=(self.header + '\n' + self.contents[self.page - 1]) or None,
                                      embed=self.embeds[self.page - 1],
                                      components=(await self._make_buttons()))

            except asyncio.TimeoutError:
                if self.delete_after_timeout:
                    return await self._message.delete()

    async def _make_buttons(self) -> list:
        """Create the actionrow used to manage the Paginator"""
        left_disable = self.page == 1
        right_disable = self.page == (len(self.embeds or self.contents))

        buttons = [
            create_button(
                style=self.left_button_style,
                label=self._left_button,
                custom_id="_left_click",
                disabled=left_disable,
            ),
            create_button(
                style=ButtonStyle.gray,
                label=f"Page {str(self.page)} / {str(len(self.embeds or self.contents))}",
                custom_id="_show_page",
                disabled=True,
            ),
            create_button(
                style=self.right_button_style,
                label=self._right_button,
                custom_id="_right_click",
                disabled=right_disable,
            ),
        ]

        if self.use_extend:
            buttons.insert(0, create_button(
                    style=self.left_button_style,
                    label=self._left2_button,
                    custom_id="_extend_left_click",
                    disabled=left_disable,
                ))
            buttons.append(create_button(
                style=self.right_button_style,
                label=self._right2_button,
                custom_id="_extend_right_click",
                disabled=right_disable,
            ))

        return [create_actionrow(*buttons)]
