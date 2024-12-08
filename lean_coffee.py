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
                r"^Continue discussing topic: (.*)\?$", message
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

        if lc == None:
            return "Cannot create LeanCoffeeBackend as one is ongoing"

        return "Creating LeanCoffee in {} with max_votes={}".format(
            message.to, max_votes
        )

    @re_botcmd(pattern=r"^# Topic: (.*)$", prefixed=False)
    def create_topic(self, message, match):
        lc = GetLeanCoffee(message.to.id)
        if lc == None:
            return "LeanCoffee is not created"

        topic = match.group(1)
        lc.CreateTopic(
            message.extras["id"], topic, message.frm.userid, message.frm.username
        )
        return "Creating Topic: {} in {}".format(match.group(1), message.to)

    @botcmd
    def lc_finalize(self, message, args):
        lc = GetLeanCoffee(message.to.id)
        if lc == None:
            return "LeanCoffee is not created"

        # Only coordinator can do so
        if message.frm.userid != lc.coordinator_id:
            return "Not coordinator, aborted"

        lc.FinalizeTopics()
        topics = lc.GetSortedTopics("FULL")

        topic_strs = [
            "- @{}: {}; votes={}".format(topic.author.name, topic.content, topic.votes)
            for topic in topics
        ]
        return "\n".join(topic_strs)

    @arg_botcmd("time", type=int, unpack_args=False)
    def lc_next(self, message, args):
        lc = GetLeanCoffee(message.to.id)
        if lc == None:
            yield "LeanCoffee is not created"
            return

        # Only coordinator can do so
        if message.frm.userid != lc.coordinator_id:
            yield "Not coordinator, aborted"
            return

        topic = lc.GetNextTopic()

        if not topic:
            yield "No more topics"
            return

        yield "Discussing {} for {} minutes".format(topic.content, args.time)
        sleep(args.time)  # use second for now
        if lc.GetCurrentTopic() == topic:
            yield "Continue discussing topic: {}?".format(topic.content)
