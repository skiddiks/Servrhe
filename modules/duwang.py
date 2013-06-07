# -*- coding: utf-8 -*-

from collections import deque
import random

dependencies = []

data = u"""
we cannot be firends when we are doubting.
I have in my htough a terror!
Joey Jojo is a ball catch!
[inaudible]
when I accidentally too much
A dead donny mnust not be seen.
啊
啊!
啊!!!
啊!!
Abaj!
Why is a noise in the furnace?
Mades always doing this.
I AM GOING TO VITCOTY!
I was hit painful
I will soon viccotry!
When JoeyJ ojo does not win me
I must punching fight him as a gentlemen.
I will poke your eye aga
Be a man and not a jealous instead!
and so you want punch  fighting match for revenge!
and I donot care what itis!
WHo tells him what happens?
FUCK DAMN SHIT CUNTS!
Nearby is a water to use.
CURSE U MUD WATER!!
I will all of his friends!!!
However I do, I am successful!
Are you kissing Joey Jojo already?
he is doing things that we are not!!
I am doing him bad but he is still happy?
U a friend of Joey JOjo.
stop being bad Joey Jojo!
This a girl Erina
so joey jojo became love with her!
both have no friends
Joey Jojo thought about loves.
SUch sweetg girls like this.
please be coming by more?
I am seeing her again from somewhere.
Dio is always making hard on my life.
DIIIIOOOOO!!!
The damned Dio.
Dio tells a lies and then lies go to others!
Joey Jojo Always tells everything!
You tell everything and a nerd.!!
Donot go!
I am giving Joey no friends or socials
I DID NOT KNO!!!
U have good punch fighting technigh DIO!
this my punvh!!
いただきます
hE is dodgin??
The first to punch face of other is victory!
Dio Burawndo is now his fight!
NO JOEY JOJO!
And so this begins Dio the Jojo.
Do not like doogs.
please listne Joey
stop the help!
you are not cool enough to touch things
WHAT U DOING
and do not fight more about dog Donny.
Mr. Jojo you are a big gratitude
Is thisfighting?
R u Dio Burawndo.
Even the MR> Jojo.
U JERK.
gentleman fight anything if need.
sp u can liv ther.
I hate the rich but i dont hate them!
act like a clown and get knocked down.
is it being like real people?
AND GO HOME WITH IT LITTLE BOY!
Joey wat r u doing at the table.
NO U DUMB IDIOTT!
i am a hero now for his!
who r u for I am sleepin again soon...
My nam is, ( u dont need to remember) Jojo.
thank you but wher am i/.
We sell teeth! for alots of mony!
she became dead for it to stay living.
If only no mud. Curse yu mud!
Sad I he is died.
This peopl fell on cliff!
He looks like gentleman.
you're grounded too speedbump
we can be courage bugs if we dont be about scared
oops gotta be a courage bug
how woody are the wood chucks...
i bet theyr pretty woody
RIPPLE MAGIC KUNG FU ACTION!
heavy rocks are not even heavy rocks now !
helping u is a gentlemen's jojob
if you smash the zombie monster brain it forgets how to come back
you have a kung fu?
go go Jack in the Box!
i smell somethin like a bad smell..
I used to be a Joey Jojo like you once too.
what a beautiful Duwang
"""

class Module(object):
    def __init__(self, master):
        self.master = master
        self.forward = {}
        self.reverse = {}
        self.load()

    def stop(self):
        pass

    def load(self):
        phrases = data.strip().split("\n")
        for p in phrases:
            self.learn(p)
    
    def learn(self, phrase):
        words = phrase.split(" ")
        c1 = [None] + words
        c2 = words + [None]
        chain = zip(c1, c2)

        for w1, w2 in chain:
            if w1 not in self.forward:
                self.forward[w1] = []
            self.forward[w1].append(w2)

            if w2 not in self.reverse:
                self.reverse[w2] = []
            self.reverse[w2].append(w1)

    def ramble(self, seed=None):
        message = deque()

        word = seed
        while word is not None and len(message) < 80:
            message.appendleft(word)
            word = self.prev(word)

        word = self.next(seed)
        while word is not None and len(message) < 80:
            message.append(word)
            word = self.next(word)
            if word is None and len(message) < 8:
                word = self.next(word)

        message = list(message)
        response = u" ".join(message)
        if len(response) > 320:
            response = response[:320] + u"..."
        if response == seed:
            response = self.ramble()
        return response

    def next(self, seed):
        if seed not in self.forward:
            return None
        return random.choice(self.forward[seed])

    def prev(self, seed):
        if seed not in self.reverse:
            return None
        return random.choice(self.reverse[seed])
