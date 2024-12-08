from enum import Enum


class Attendee:

    def __init__(self, id: str, name: str, max_votes: int):
        self.id = id
        self.name = name
        self.max_votes = max_votes
        self.authored_topics = []
        self.voted_topics = []
        self.valid_voted_topics = []

    def Vote(self, topic_id):
        self.voted_topics.append(topic_id)
        self.valid_voted_topics = self.voted_topics[:self.max_votes]

    def Unvote(self, topic_id):
        self.voted_topics.remove(topic_id)
        self.valid_voted_topics = self.voted_topics[:self.max_votes]


class Topic:

    def __init__(self, id: str, content: str, author: Attendee):
        self.id = id
        self.content = content
        self.author = author
        self.author.authored_topics.append(self)
        self.voters = []
        self.votes = 0


class LeanCoffeeBackend:

    class Status(Enum):
        CREATED = 1
        DISCUSSING = 2
        FINISHED = 3

    def __init__(self, coordinator_id: str, max_votes: int):
        self.status = LeanCoffeeBackend.Status.CREATED
        self.max_votes = max_votes
        self.coordinator_id = coordinator_id
        self.attendee = {}
        self.topics = {}
        self.sorted_topics = []
        self.current_topic_index = 0

    def SetStatus(self, status: Status):
        self.status = status

    def GetAttendee(self, name: str, id: str):
        if id in self.attendee:
            return self.attendee[id]
        attendee = Attendee(name, id, self.max_votes)
        self.attendee[id] = attendee
        return attendee

    def CreateTopic(self, topic_id: str, content: str, author_id: str,
                    author_name: str):
        if self.status != LeanCoffeeBackend.Status.CREATED:
            return
        author = self.GetAttendee(author_name, author_id)
        topic = Topic(topic_id, content, author)
        self.topics[id] = topic

    def AttendeeVote(self, topic_id: str, attendee_id: str,
                     attendee_name: str):
        if self.status != LeanCoffeeBackend.Status.CREATED:
            return
        if topic_id not in self.topics:
            return
        self.GetAttendee(attendee_name, attendee_id).Vote(topic_id)

    def AttendeeUnvote(self, topic_id: str, attendee_id: str,
                       attendee_name: str):
        if self.status != LeanCoffeeBackend.Status.CREATED:
            return
        if topic_id not in self.topics:
            return
        self.GetAttendee(attendee_name, attendee_id).Unvote(topic_id)

    def FinalizeTopics(self):
        if self.status != LeanCoffeeBackend.Status.CREATED:
            return
        for attendee in self.attendee.values():
            for topic_id in attendee.valid_voted_topics:
                self.topics[topic_id].voters.append(attendee)
                self.topics[topic_id].votes += 1

        self.sorted_topics = sorted(self.topics.values(),
                                    key=lambda x: x.votes,
                                    reverse=True)
        self.status = LeanCoffeeBackend.Status.DISCUSSING

    # type: FULL, FINISHED, UNFINISHED
    def GetSortedTopics(self, fetch_type: str):
        if self.status != LeanCoffeeBackend.Status.DISCUSSING:
            return []
        if fetch_type == "FULL":
            return self.sorted_topics
        elif fetch_type == "FINISHED":
            return self.sorted_topics[:self.current_topic_index]
        elif fetch_type == "UNFINISHED":
            return self.sorted_topics[self.current_topic_index + 1:]

    def GetCurrentTopic(self):
        if self.status != LeanCoffeeBackend.Status.DISCUSSING:
            return None
        if self.current_topic_index >= len(self.sorted_topics):
            self.status = LeanCoffeeBackend.Status.FINISHED
            return None
        return self.sorted_topics[self.current_topic_index]

    def GetNextTopic(self):
        if self.status != LeanCoffeeBackend.Status.DISCUSSING:
            return None
        if self.current_topic_index >= len(self.sorted_topics):
            self.status = LeanCoffeeBackend.Status.FINISHED
            return None
        topic = self.sorted_topics[self.current_topic_index]
        self.current_topic_index += 1
        return topic


ongoing_lean_coffees = {}


def GetLeanCoffee(channel_id: str) -> LeanCoffeeBackend:
    return ongoing_lean_coffees.get(channel_id, None)


def CreateLeanCoffee(channel_id: str, coordinator_id: str,
                     max_votes: int) -> LeanCoffeeBackend | None:
    if GetLeanCoffee(channel_id) is not None:
        return None
    lean_coffee = LeanCoffeeBackend(coordinator_id, max_votes)
    ongoing_lean_coffees[channel_id] = lean_coffee
    return lean_coffee
