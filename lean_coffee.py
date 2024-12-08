import logging
import re
from time import sleep
from errbot import BotPlugin, arg_botcmd, botcmd, re_botcmd, webhook
from errbot.backends.base import (
    REACTION_ADDED,
    REACTION_REMOVED,
)

from lib.lean_coffee_backend import *

log = logging.getLogger("errbot.plugins.lean_coffee")


class LeanCoffee(BotPlugin):
    """
    Run Lean Coffee with Errbot
    """

    def activate(self):
        """
        Triggers on plugin activation

        You should delete it if you're not using it to override any default behaviour
        """
        super(LeanCoffee, self).activate()

    def deactivate(self):
        """
        Triggers on plugin deactivation

        You should delete it if you're not using it to override any default behaviour
        """
        super(LeanCoffee, self).deactivate()

    def check_configuration(self, configuration):
        """
        Triggers when the configuration is checked, shortly before activation

        Raise a errbot.ValidationException in case of an error

        You should delete it if you're not using it to override any default behaviour
        """
        super(LeanCoffee, self).check_configuration(configuration)

    def callback_reaction(self, reaction):
        lc = GetLeanCoffee(reaction.reacted_to_owner.id)
        if not lc:
            return

        if lc.status == LeanCoffeeBackend.Status.CREATED:
            if reaction.action == REACTION_ADDED:
                lc.AttendeeVote(
                    reaction.reacted_to["id"],
                    reaction.reactor.userid,
                    reaction.reactor.username,
                )
            elif reaction.action == REACTION_REMOVED:
                lc.AttendeeUnvote(
                    reaction.reacted_to["id"],
                    reaction.reactor.userid,
                    reaction.reactor.username,
                )
            elif reaction.action == "post_deleted":
                lc.DeleteTopic(reaction.reacted_to["id"])

        elif lc.status == LeanCoffeeBackend.Status.DISCUSSING:
            if reaction.reacted_to["user_id"] != self.bot_identifier.userid:
                # self.send(reaction.reacted_to_owner, "Not from bot itself, ignored")
                return

            message = reaction.reacted_to["message"]
            is_continue_question = re.match(
                r"^## @all Continue discussing topic: \"(.*)\"\?$", message
            )
            if not is_continue_question:
                # self.send(reaction.reacted_to_owner, "Not a continue question, ignored")
                return

            content = is_continue_question.group(1)

            cur_topic = lc.GetCurrentTopic()
            if content != cur_topic.content:
                # self.send(reaction.reacted_to_owner, "Not current topic, ignored")
                return

            if reaction.action == REACTION_ADDED:
                if reaction.reaction_name == "+1":
                    cur_topic.AddContinueUpvote()
                elif reaction.reaction_name == "-1":
                    cur_topic.AddContinueDownvote()
            elif reaction.action == REACTION_REMOVED:
                if reaction.reaction_name == "+1":
                    cur_topic.RemoveContinueUpvote()
                elif reaction.reaction_name == "-1":
                    cur_topic.RemoveContinueDownvote()

    @arg_botcmd(
        "--max-votes",
        type=int,
        choices=range(1, 10),
        default=3,
        unpack_args=False,
        help="max votes per person",
    )
    def lc_create(self, message, args):
        """Create a Lean Coffee session"""
        max_votes = args.max_votes
        lc = CreateLeanCoffee(message.to.id, message.frm.userid, max_votes)

        if not lc:
            return "Cannot create Lean Coffee as one is ongoing"

        return (
            "## Lean Coffee created :coffee:\n"
            "### Rules\n"
            "- Coordinator: @{}\n"
            "- Max votes per person: {}\n"
            "### Hints\n"
            "- Create topics with [H1 headings](https://docs.mattermost.com/collaborate/format-messages.html#id2)\n"
            "- Delete a topic by [deleting the post](https://docs.mattermost.com/collaborate/send-messages.html#delete-messages)\n"
            "- Vote for topics by [reacting with emojis](https://docs.mattermost.com/collaborate/react-with-emojis-gifs.html)\n"
            "- React :+1: for continuing the topic and :-1: for ending one\n"
        ).format(message.frm.username, max_votes)

    @botcmd
    def lc_abort(self, message, args):
        """Abort a Lean Coffee session"""
        lc = GetLeanCoffee(message.to.id)
        if not lc:
            return "Lean Coffee is not created"

        # Only coordinator can do so
        if message.frm.userid != lc.coordinator_id:
            return "Not coordinator, aborted"

        lc.AbortLeanCoffee()
        return "Aborted"

    @re_botcmd(pattern=r"^#\s+(.*)$", prefixed=False)
    def create_topic(self, message, match):
        """Add a topic using H1 heading syntax"""
        lc = GetLeanCoffee(message.to.id)
        if not lc:
            return

        topic = match.group(1)
        lc.CreateTopic(
            message.extras["id"], topic, message.frm.userid, message.frm.username
        )

    @botcmd
    def lc_finalize(self, message, args):
        """Finalize topics to discuss"""
        lc = GetLeanCoffee(message.to.id)
        if not lc:
            return "Lean Coffee is not created"

        # Only coordinator can do so
        if message.frm.userid != lc.coordinator_id:
            return "Not coordinator, aborted"

        if lc.status > LeanCoffeeBackend.Status.CREATED:
            return "Cannot finalize during discussion"

        lc.FinalizeTopics()
        topics = lc.GetSortedTopics("FULL")

        if not topics:
            lc.AbortLeanCoffee()
            return "No topics to discuss, aborted"

        for topic in topics:
            self.send_card(
                to=message.frm,
                title="@{} wants to discuss".format(topic.author.name),
                body="# {}".format(topic.content),
                fields=(
                    (
                        "Interested by:",
                        " ".join(["@{}".format(voter.name) for voter in topic.voters]),
                    ),
                ),
                color="blue",
            )

    @arg_botcmd(
        "time",
        type=float,
        nargs="?",
        default=5.0,
        unpack_args=False,
        help="minutes to discuss",
    )
    def lc_next(self, message, args):
        """Discuss next topic for <time> minutes"""
        lc = GetLeanCoffee(message.to.id)
        if not lc:
            yield "Lean Coffee is not created"
            return

        # Only coordinator can do so
        if message.frm.userid != lc.coordinator_id:
            yield "Not coordinator, aborted"
            return

        if lc.status < LeanCoffeeBackend.Status.DISCUSSING:
            yield "Do !lc finalize first"
            return

        if args.time < 0.0:
            yield "Invalid time"
            return

        seconds = args.time * 60  # time is in minutes
        topic = lc.GetNextTopic()

        if not topic:
            topics = lc.GetSortedTopics("FULL")
            body = (
                "# :tada: Congratulation! :pedro:\n---\n"
                + "### Topics disscussed\n{}".format(
                    "\n".join(
                        [
                            "- @{}: {} ({}) [{}]".format(
                                topic.author.name,
                                topic.content,
                                topic.votes,
                                topic.GetDiscussedTime(),
                            )
                            for topic in topics
                        ]
                    )
                )
            )

            self.send_card(
                to=message.frm,
                title="Lean Coffee finished",
                body=body,
                fields=(
                    (
                        "Lean Coffee time:",
                        "{}".format(lc.GetLeanCoffeeTime()),
                    ),
                    (
                        "Topics disscussed:",
                        "{}".format(len(topics)),
                    ),
                ),
                color="green",
            )
            return

        self.send_card(
            to=message.frm,
            title="Now discussing",
            body="# {}".format(topic.content),
            fields=(
                (
                    "Scheduled:",
                    strftime("%H:%M:%S", gmtime(seconds)),
                ),
                (
                    "Elapsed:",
                    "{}".format(topic.GetElapsedTime()),
                ),
            ),
            color="red",
        )
        sleep(seconds)
        cur_topic = lc.GetCurrentTopic()
        if cur_topic and cur_topic == topic:
            yield '## @all Continue discussing topic: "{}"?'.format(topic.content)

    @botcmd
    def lc_summarize(self, message, args):
        """Summarize discussed topics"""
        lc = GetLeanCoffee(message.to.id)
        if not lc:
            return "Lean Coffee is not created"

        topics = lc.GetSortedTopics("FINISHED")

        if not topics:
            return

        for topic in topics:
            self.send_card(
                to=message.frm,
                title="@{} wanted to discuss".format(topic.author.name),
                body="# {}".format(topic.content),
                fields=(
                    (
                        "Interested by:",
                        " ".join(["@{}".format(voter.name) for voter in topic.voters]),
                    ),
                    (
                        "Discussed:",
                        "{}".format(topic.GetDiscussedTime()),
                    ),
                ),
                color="green",
            )

    @botcmd
    def lc_queue(self, message, args):
        """Show the topics queue"""
        lc = GetLeanCoffee(message.to.id)
        if not lc:
            return "Lean Coffee is not created"

        topics = lc.GetSortedTopics("UNFINISHED")

        if not topics:
            return

        for topic in topics:
            self.send_card(
                to=message.frm,
                title="@{} wants to discuss".format(topic.author.name),
                body="# {}".format(topic.content),
                fields=(
                    (
                        "Interested by:",
                        " ".join(["@{}".format(voter.name) for voter in topic.voters]),
                    ),
                ),
                color="blue",
            )
