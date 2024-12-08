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

    def get_configuration_template(self):
        """
        Defines the configuration structure this plugin supports

        You should delete it if your plugin doesn't use any configuration like this
        """
        return {
            "EXAMPLE_KEY_1": "Example value",
            "EXAMPLE_KEY_2": ["Example", "Value"],
        }

    def check_configuration(self, configuration):
        """
        Triggers when the configuration is checked, shortly before activation

        Raise a errbot.ValidationException in case of an error

        You should delete it if you're not using it to override any default behaviour
        """
        super(LeanCoffee, self).check_configuration(configuration)

    def callback_connect(self):
        """
        Triggers when bot is connected

        You should delete it if you're not using it to override any default behaviour
        """
        pass

    def callback_message(self, message):
        """
        Triggered for every received message that isn't coming from the bot itself

        You should delete it if you're not using it to override any default behaviour
        """
        pass

    def callback_botmessage(self, message):
        """
        Triggered for every message that comes from the bot itself

        You should delete it if you're not using it to override any default behaviour
        """
        pass

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
        elif lc.status == LeanCoffeeBackend.Status.DISCUSSING:
            if reaction.reacted_to["user_id"] != self.bot_identifier.userid:
                # self.send(reaction.reacted_to_owner, "Not from bot itself, ignored")
                return

            message = reaction.reacted_to["message"]
            is_continue_question = re.match(
                r"^## @all Continue discussing topic: (.*)\?$", message
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

    @webhook
    def example_webhook(self, incoming_request):
        """A webhook which simply returns 'Example'"""
        return "Example"

    @arg_botcmd("--max-votes", type=int, unpack_args=False)
    def lc_create(self, message, args):
        max_votes = abs(args.max_votes or 3)
        lc = CreateLeanCoffee(message.to.id, message.frm.userid, max_votes)

        if not lc:
            return "Cannot create LeanCoffeeBackend as one is ongoing"

        return "Creating LeanCoffee in {} with max_votes={}".format(
            message.to, max_votes
        )

    @botcmd
    def lc_abort(self, message, args):
        lc = GetLeanCoffee(message.to.id)
        if not lc:
            return "LeanCoffee is not created"

        # Only coordinator can do so
        if message.frm.userid != lc.coordinator_id:
            return "Not coordinator, aborted"

        lc.AbortLeanCoffee()

    @re_botcmd(pattern=r"^#\s+(.*)$", prefixed=False)
    def create_topic(self, message, match):
        lc = GetLeanCoffee(message.to.id)
        if not lc:
            return

        topic = match.group(1)
        lc.CreateTopic(
            message.extras["id"], topic, message.frm.userid, message.frm.username
        )

    @botcmd
    def lc_finalize(self, message, args):
        lc = GetLeanCoffee(message.to.id)
        if not lc:
            return "LeanCoffee is not created"

        # Only coordinator can do so
        if message.frm.userid != lc.coordinator_id:
            return "Not coordinator, aborted"

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

    @arg_botcmd("-t", type=int, unpack_args=False)
    def lc_next(self, message, args):
        lc = GetLeanCoffee(message.to.id)
        if not lc:
            yield "LeanCoffee is not created"
            return

        # Only coordinator can do so
        if message.frm.userid != lc.coordinator_id:
            yield "Not coordinator, aborted"
            return

        time = abs(args.t or 5)
        topic = lc.GetNextTopic()

        if not topic:
            topics = lc.GetSortedTopics("FULL")
            body = (
                "# :tada: Congratulation :pedro:\n---\n"
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
                    "{} minutes".format(time),
                ),
                (
                    "Elapsed:",
                    "{}".format(topic.GetElapsedTime()),
                ),
            ),
            color="red",
        )
        sleep(time)  # use second for now
        cur_topic = lc.GetCurrentTopic()
        if cur_topic and cur_topic == topic:
            yield "## @all Continue discussing topic: {}?".format(topic.content)

    @botcmd
    def lc_summarize(self, message, args):
        lc = GetLeanCoffee(message.to.id)
        if not lc:
            return "LeanCoffee is not created"

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
        lc = GetLeanCoffee(message.to.id)
        if not lc:
            return "LeanCoffee is not created"

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
