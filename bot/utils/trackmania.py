import country_converter as coco
import flag
import json
from datetime import datetime, timezone, timedelta
import threading
import wget
import os
import requests
import shutil

import discord

from bot.utils.database import Database
from bot.utils.commons import add_commas, get_random_color, format_seconds
from bot.utils.discord import easy_embed as ezembed

from bot.api import APIClient
from bot.log import get_logger

log = get_logger(__name__)


class TrackmaniaUtils:
    """Functions relating to a specific Trackmania player who is given while creating the object"""

    def __init__(self, username: str):
        self.username = username
        self.api_client = APIClient()

    async def close(self):
        """Closes the API Client"""
        await self.api_client.close()
        return

    async def get_id(self) -> str:
        """Gets the ID of the Player from the API

        Raises:
            NotAValidUsername: If the username is not valid, this exception is raised.

        Returns:
            str: The ID of the player
        """
        log.debug("Checking if the ID is in the file")
        id = Database.retrieve_id(self.username)

        if id is None:
            log.debug("Getting the data from the TMIndiaBotAPI")
            id_data = await self.api_client.get(
                f"http://localhost:3000/tm2020/player/{self.username}/id"
            )

            try:
                id = id_data["id"]
            except KeyError:
                id = None

            log.debug("Storing the Username and ID to the file")
            Database.store_id(self.username, id)

        else:
            log.debug("Username exists in file")

        return id

    async def get_player_data(self, player_id: str) -> list[discord.Embed]:
        log.debug(f"Getting Data for {player_id}")
        raw_player_data = await self.api_client.get(
            f"http://localhost:3000/tm2020/player/{player_id}"
        )

        log.debug("Getting Player Flag Unicode")
        player_flag_unicode = self._get_player_country_flag(raw_player_data)
        log.debug(f"Got Player Unicode flag -> {player_flag_unicode}")

        display_name = raw_player_data["displayname"]
        log.debug(f"Display Name is {display_name}")

        log.debug("Checking if Player has Played the Game")
        if raw_player_data["trophies"]["points"] == 0:
            return [
                ezembed.create_embed(
                    title=f"{player_flag_unicode} {display_name} has never played Trackmania 2020",
                    color=0xFF0000,
                )
            ]

        log.debug("Creating Two Embeds")
        page_one = ezembed.create_embed(
            title=f"Player Data for {player_flag_unicode} {display_name} - Page 1",
            color=get_random_color(),
        )
        page_two = ezembed.create_embed(
            title=f"Player Data for {player_flag_unicode} {display_name} - Page 2",
            color=get_random_color(),
        )
        page_three = ezembed.create_embed(
            title=f"Player Data for {player_flag_unicode} {display_name} - Page 3",
            color=get_random_color(),
        )

        zones, zone_ranks = self._get_zones_and_positions(raw_player_data)
        royal_data = self._get_royal_data(raw_player_data)
        matchmaking_data = self._get_matchmaking_data(raw_player_data)
        trophy_count = self._get_trophy_count(raw_player_data)

        log.debug("Adding Zones and Zone Ranks to Page One")
        page_one.add_field(name="Zones", value=zones, inline=False)
        page_one.add_field(name="Zone Ranks", value=zone_ranks, inline=False)

        log.debug("Adding Matchmaking and Royal Data to Page Two")
        page_two.add_field(name="Matchmaking", value=matchmaking_data, inline=False)
        page_two.add_field(name="Royal", value=royal_data, inline=False)

        log.debug("Adding Trophy Count to Page Three")
        page_three.add_field(name="Trophy Count", value=trophy_count, inline=False)

        try:
            log.debug("Adding Meta Data to Page One")
            page_one = self._add_meta_details(page_one, raw_player_data)
            log.debug("Added Meta Data to Page One")
        except:
            log.debug("Player does not have Meta Data")

        log.debug(f"Returning {page_one}, {page_two} and {page_three}")
        return [page_one, page_two, page_three]

    def _get_player_country_flag(self, raw_player_data):
        log.debug("Getting Zones")

        try:
            zone_one = raw_player_data["trophies"]["zone"]["name"]
            zone_two = raw_player_data["trophies"]["zone"]["parent"]["name"]

            log.debug(f"Zones -> {zone_one} and {zone_two}")

            continents = (
                "Asia",
                "Middle East",
                "Europe",
                "North America",
                "South America",
                "Africa",
            )

            if zone_two in continents:
                log.debug("Only First Zone is Required")
                iso_letters = coco.convert(names=[zone_one], to="ISO2")
                unicode_letters = flag.flag(iso_letters)
            else:
                log.debug("Need to use Zone Two")
                iso_letters = coco.convert(names=[zone_two], to="ISO2")
                unicode_letters = flag.flag(iso_letters)

            log.debug(f"Unicode Letters are {unicode_letters}")
            return unicode_letters
        except:
            log.error("Player has never played Trackmania 2020")
            return ":flag_white:"

    def _get_royal_data(self, raw_player_data) -> str:
        log.debug("Getting Player Data")

        try:
            royal_data = raw_player_data["matchmaking"][1]

            rank = royal_data["info"]["rank"]
            wins = royal_data["info"]["progression"]
            current_div = royal_data["info"]["division"]["position"]

            if wins != 0:
                progression_to_next_div = (
                    round(
                        (wins - royal_data["info"]["division"]["minwins"])
                        / (
                            royal_data["info"]["division"]["maxwins"]
                            - royal_data["info"]["division"]["minwins"]
                            + 1
                        ),
                        4,
                    )
                    * 100
                )
            else:
                log.debug("Player Has Not Won a Single Royal Match")
                progression_to_next_div = "0"

            log.debug(
                f"Creating Royal Data String with {rank}, {wins}, {current_div} and {progression_to_next_div}"
            )
            royal_data_string = f"```Rank: {rank}\nWins: {wins}\nCurrent Division: {current_div}\nProgression to Next Division: {progression_to_next_div}%```"

            log.debug(f"Created Royal Data String -> {royal_data_string}")
            return royal_data_string
        except:
            return (
                "An Error Occured While Getting Royal Data, Player has not played Royal"
            )

    def _get_matchmaking_data(self, raw_player_data) -> str:
        log.debug("Getting Matchmaking Data")

        try:
            matchmaking_data = raw_player_data["matchmaking"][0]

            rank = matchmaking_data["info"]["rank"]
            score = matchmaking_data["info"]["score"]
            current_div = int(matchmaking_data["info"]["division"]["position"])

            log.debug("Opening the MM Ranks File")
            with open(
                "./bot/resources/json/mm_ranks.json", "r", encoding="UTF-8"
            ) as file:
                mm_ranks = json.load(file)
                current_div = mm_ranks["rank_data"][str(current_div - 1)]

            log.debug("Calculating Progression to Next Division")
            progression_to_next_div = (
                round(
                    (score - matchmaking_data["info"]["division"]["minpoints"])
                    / (
                        matchmaking_data["info"]["division"]["maxpoints"]
                        - matchmaking_data["info"]["division"]["minpoints"]
                        + 1
                    ),
                    4,
                )
                * 100
            )

            log.debug(
                f"Creating Matchmaking Data String with {rank}, {score}, {current_div}, {progression_to_next_div}"
            )
            matchmaking_data_string = f"```Rank: {rank}\nScore: {score}\nCurrent Division: {current_div}\nProgression to Next Division: {progression_to_next_div}%```"

            log.debug(f"Created Matchmaking Data String -> {matchmaking_data_string}")
            return matchmaking_data_string
        except:
            log.error("Player has never Played Matchmaking")
            return "An error Occured While Getting Matchmaking Data, Player has not played Matchmaking"

    def _get_trophy_count(self, raw_player_data) -> str:
        log.debug("Getting Trophy Counts")
        trophy_count_string = "```\n"

        log.debug("Adding Total Points")
        total_points = add_commas(raw_player_data["trophies"]["points"])
        trophy_count_string += f"Total Points: {total_points}\n\n"
        log.debug(f"Added Total Points -> {total_points}")

        for i, trophy_count in enumerate(raw_player_data["trophies"]["counts"]):
            trophy_count_string = (
                trophy_count_string + f"Trophy {i + 1}: {trophy_count}\n"
            )
        trophy_count_string += "```"

        log.debug(f"Final Trophy Count -> {trophy_count_string}")
        return trophy_count_string

    def _get_zones_and_positions(self, raw_player_data) -> str:
        """
        Converts raw_player_data into location and their ranks
        """
        ranks_string = ""

        log.debug("Getting Zones")
        zone_one = raw_player_data["trophies"]["zone"]["name"]
        zone_two = raw_player_data["trophies"]["zone"]["parent"]["name"]
        zone_three = raw_player_data["trophies"]["zone"]["parent"]["parent"]["name"]

        try:
            zone_four = raw_player_data["trophies"]["zone"]["parent"]["parent"][
                "parent"
            ]["name"]
        except:
            zone_four = ""

        log.debug(f"Got Zones -> {zone_one}, {zone_two}, {zone_three}, {zone_four}")
        log.debug("Getting Position Data")
        raw_zone_positions = raw_player_data["trophies"]["zonepositions"]
        zone_one_position = raw_zone_positions[0]
        zone_two_position = raw_zone_positions[1]
        zone_three_position = raw_zone_positions[2]

        if zone_four != "":
            zone_four_position = raw_zone_positions[3]
        else:
            zone_four_position = -1

        log.debug("Got Position Data")
        log.debug("Making string for position data")
        ranks_string = "```\n"
        ranks_string += f"{zone_one} - {zone_one_position}\n"
        ranks_string += f"{zone_two} - {zone_two_position}\n"
        ranks_string += f"{zone_three} - {zone_three_position}\n"

        if zone_four != "":
            ranks_string += f"{zone_four} - {zone_four_position}\n"

        ranks_string += "```"

        log.debug(f"Final Ranks String is {ranks_string}")

        log.debug("Creating Zones String")
        zones_string = f"```\n{zone_one}, {zone_two}, {zone_three}"

        if zone_four != "":
            zones_string += f", {zone_four}"

        zones_string += "\n```"

        return zones_string, ranks_string

    def _add_meta_details(
        self,
        player_page: discord.Embed,
        raw_player_data,
    ) -> discord.Embed:
        log.debug("Adding Meta Details for Player")

        meta_data = raw_player_data["meta"]

        try:
            log.debug("Checking if Player has Twitch")
            twitch_name = meta_data["twitch"]
            player_page.add_field(
                name="[<:twitch:895250576751853598>] Twitch",
                value=f"[{twitch_name}](https://twitch.tv/{twitch_name})",
                inline=True,
            )
            log.debug("Twitch Added for Player")
        except:
            log.debug("Player does not have a Twitch Account Linked to TMIO")

        try:
            log.debug("Checking if Player has Twitter")
            twitter_name = meta_data["twitter"]
            player_page.add_field(
                name="[<:twitter:895250587157946388>] Twitter",
                value=f"    [{twitter_name}](https://twitter.com/{twitter_name})",
                inline=True,
            )
            log.debug("Twitter Added for Player")
        except:
            log.debug("Player does not have a Twitter Account Linked to TMIO")

        try:
            log.debug("Checking if Player has YouTube")
            youtube_link = meta_data["youtube"]
            player_page.add_field(
                name="[<:youtube:895250572599513138>] YouTube",
                value=f"[YouTube](https://youtube.com/channel/{youtube_link})",
                inline=True,
            )
            log.debug("YouTube Added for Player")
        except:
            log.debug("Player does not have a YouTube Account Linked to TMIO")

        log.debug("Adding TMIO")
        display_name = raw_player_data["displayname"]
        player_id = raw_player_data["accountid"]
        player_page.add_field(
            name="TMIO",
            value=f"[{display_name}](https://trackmania.io/#/player/{player_id})",
        )

        try:
            log.debug("Checking if TMGL Player")
            if meta_data["tmgl"] is True:
                player_page.add_field(
                    name="TMGL", value="This Player Participates in TMGL", inline=True
                )
                log.debug("Added TMGL Field")
        except:
            log.debug("Player does not participate in TMGL")

        log.debug("Added TMIO Link")
        log.debug(f"Returning {player_page}")
        return player_page


class TOTDUtils:
    @staticmethod
    def _download_thumbail(url: str) -> None:
        if os.path.exists("./bot/resources/temp/totd.png"):
            log.debug("Thumbnail already downloaded")
            return

        req = requests.get(url, stream=True)

        if req.status_code == 200:
            log.debug("Image was retrieved succesfully")
            req.raw.decode_content = True

            log.debug("Saving Image to File")
            with open("./bot/resources/temp/totd.png", "wb") as file:
                shutil.copyfileobj(req.raw, file)
        else:
            log.critical("Image could not be retrieved")

    @staticmethod
    def _parse_mx_tags(self, tags: str) -> str:
        log.debug(f"Tags -> {tags}")
        log.debug("Removing Spaces")
        tags.replace(" ", "")
        log.debug(f"Without Spaces -> {tags}")

        tags = tags.split(",")

        tag_string = ""

        with open("./bot/resources/json/mxtags.json", "r") as file:
            mxtags = json.load(file)["mx"]

            for i, tag in enumerate(tags):
                log.debug(f"Converting {tag}")

                for j in range(len(mxtags)):
                    if int(tag) == int(mxtags[j]["ID"]):
                        tag_string = tag_string + mxtags[j]["Name"] + ", "

        log.debug(f"Tag String -> {tag_string}")
        return tag_string[:-2]

    @staticmethod
    async def today():
        log.info("Creating an API Client")
        api_client = APIClient()
        log.info("Created an API Client")

        log.debug("Getting TOTD Data from API")
        totd_data = await api_client.get("http://localhost:3000/tm2020/totd/latest")

        log.debug("Parsing TOTD Data")
        map_name = totd_data["name"]
        author_name = totd_data["authorplayer"]["name"]
        thumbnail_url = totd_data["thumbnailUrl"]

        author_time = format_seconds(int(totd_data["authorScore"]))
        gold_time = format_seconds(int(totd_data["goldScore"]))
        silver_time = format_seconds(int(totd_data["silverScore"]))
        bronze_time = format_seconds(int(totd_data["bronzeScore"]))

        nadeo_uploaded = totd_data["timestamp"]

        wr_holder = totd_data["leaderboard"]["tops"][0]["player"]["name"]
        wr_time = format_seconds(int(totd_data["leaderboard"]["tops"][0]["time"]))

        tmio_id = totd_data["mapUid"]
        log.debug("Parsed TOTD Data")

        log.debug("Parsing Download Link")
        download_link = totd_data["fileUrl"]
        log.debug("Parsed Download Link")

        log.debug("Parsing Time Uploaded to Timestamp")
        nadeo_timestamp = (
            datetime.strptime(nadeo_uploaded[:-6], "%Y-%m-%dT%H:%M:%S")
            .replace(tzinfo=timezone.utc)
            .timestamp()
        )
        log.debug("Parsed Time Uploaded to Timestamps")

        log.debug("Creating Strings from Parsed Data")
        medal_times = f"<:author:894268580902883379> {author_time}\n<:gold:894268580970004510> {gold_time}\n<:silver:894268580655411220> {silver_time}\n<:bronze:894268580181458975> {bronze_time}"
        world_record = f"Holder: {wr_holder}\nTime: {wr_time}"

        nadeo_uploaded = f"<t:{int(nadeo_timestamp)}:R>"

        log.debug("Created Strings from Parsed Data")

        log.debug(
            "Getting Map Thumbnail\nChecking if map Thumbnail has Already been Downloaded"
        )

        if not os.path.exists("./bot/resources/temp/totd.png"):
            log.critical("Map Thumbail has not been downloaded")
            TOTDUtils._download_thumbail(thumbnail_url)

        log.debug("Parsing TM Exchange Data")
        try:
            mania_tags = totd_data["exchange"]["Tags"]
            mx_uploaded = totd_data["exchange"]["UploadedAt"]
            tmx_code = totd_data["exchange"]["TrackID"]

            try:
                mx_dt = datetime.strptime(mx_uploaded[:-3], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                mx_dt = datetime.strptime(mx_uploaded[:-4], "%Y-%m-%dT%H:%M:%S")

            mx_timestamps = mx_dt.replace(tzinfo=timezone.utc).timestamp()
            mx_uploaded = f"<t:{int(mx_timestamps)}:R>"
        except:
            log.critical("Map has never been uploaded to trackmania.exchange")

        log.debug("Creating Embed")
        current_day = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime(
            "%d"
        )
        current_month = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime(
            "%B"
        )

        # Add Day Suffix
        if int(current_day) % 10 == 1:
            day_suffix = "st"
        elif int(current_day) % 10 == 2:
            day_suffix = "nd"
        elif int(current_day) % 10 == 3:
            day_suffix = "rd"
        else:
            day_suffix = "th"

        embed = ezembed.create_embed(
            title=f"Here is the {current_day}{day_suffix} {current_month} TOTD",
            color=get_random_color(),
        )
        log.debug("Creating Image File")
        image = discord.File("./bot/resources/temp/totd.png", filename="totd.png")
        embed.set_image(url="attachment://totd.png")
        embed.add_field(name="Map Name", value=map_name, inline=False)
        embed.add_field(name="Author", value=author_name, inline=True)

        try:
            embed.add_field(
                name="Tags", value=TOTDUtils._parse_mx_tags(mania_tags), inline=False
            )
        except:
            pass

        embed.add_field(
            name="Time Uploaded to Nadeo server", value=nadeo_uploaded, inline=False
        )

        try:
            embed.add_field(name="Time Uploaded to TMX", value=mx_uploaded, inline=True)
        except:
            pass

        embed.add_field(name="Medal Times", value=medal_times, inline=False)
        embed.add_field(name="Word record", value=world_record, inline=False)

        tmio_link = f"https://trackmania.io/#/leaderboard/{tmio_id}"

        try:
            tmx_link = f"https://trackmania.exchange/maps/{tmx_code}/"
        except:
            tmx_link = None

        log.debug("Created Embed")

        log.info("Closing the API Client")
        await api_client.close()
        log.info("Closed the API Embed")

        return embed, image, download_link, tmio_link, tmx_link


class NotAValidUsername(Exception):
    """Raised when the Username given is not valid.

    Args:
        Exception ([type]): [description]
    """

    def __init__(self, excp: Exception):
        self.message = excp.message

    def __str__(self):
        return self.message if self.message is not None else None
