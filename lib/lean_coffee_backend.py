class Attendee:

    def __init__(self, name: str, id: str, max_votes: int):
        self.name = name
        self.id = id
        self.max_votes = max_votes
        self.authored_posts = []
        self.voted_posts = []
        self.valid_voted_posts = []

    def Vote(self, post_id):
        self.voted_posts.append(post_id)
        self.valid_voted_posts = self.voted_posts[:self.max_votes]

    def Unvote(self, post_id):
        self.voted_posts.remove(post_id)
        self.valid_voted_posts = self.voted_posts[:self.max_votes]


class Post:

    def __init__(self, id: str, content: str, author: Attendee):
        self.id = id
        self.content = content
        self.author = author
        self.author.authored_posts.append(self)
        self.voters = []
        self.votes = 0


class LeanCoffeeBackend:

    def __init__(self, max_votes: int):
        self.max_votes = max_votes
        self.attendee = {}
        self.posts = {}
        self.sorted_posts = []
        self.current_post_index = 0

    def GetAttendee(self, name: str, id: str):
        if id in self.attendee:
            return self.attendee[id]
        attendee = Attendee(name, id, self.max_votes)
        self.attendee[id] = attendee
        return attendee

    def CreatePost(self, id: str, content: str, author_name: str,
                   author_id: str):
        author = self.GetAttendee(author_name, author_id)
        post = Post(id, content, author)
        self.posts[id] = post

    def AttendeeVote(self, post_id: str, attendee_id: str, attendee_name: str):
        if (post_id not in self.posts):
            return
        self.GetAttendee(attendee_name, attendee_id).Vote(post_id)

    def AttendeeUnvote(self, post_id: str, attendee_id: str,
                       attendee_name: str):
        if (post_id not in self.posts):
            return
        self.GetAttendee(attendee_name, attendee_id).Unvote(post_id)

    def FinalizePosts(self):
        for attendee in self.attendee.values():
            for post_id in attendee.valid_voted_posts:
                self.posts[post_id].voters.append(attendee)
                self.posts[post_id].votes += 1

        self.sorted_posts = sorted(
            self.posts.values(), key=lambda x: x.votes, reverse=True)

    def GetSortedPosts(self):
        return self.sorted_posts

    def GetNextPost(self):
        if self.current_post_index >= len(self.sorted_posts):
            return None
        post = self.sorted_posts[self.current_post_index]
        self.current_post_index += 1
        return post
