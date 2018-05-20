from random import randint, choice
import traceback
import pprint

import requests
import redis
import attr

from disconstants import *
from errors import *


@attr.s
class Game(object):
    level    = attr.ib(default=1)
    hp       = attr.ib(default=15)
    enemy    = attr.ib(default=None)
    potion   = attr.ib(default=5)
    gold     = attr.ib(default=10)
    exp      = attr.ib(default=0)
    maxdmg   = attr.ib(default=5)
    maxhp    = attr.ib(default=15)
    progress = attr.ib(default=0)
    cavloot  = attr.ib(default=0)

    def gameover(self):
        global sessions
        del sessions[self.user]

    def fight(self):
        enemy = self.enemy
        dmg = randint(0, self.maxdmg)
        if not self.enemy:
            return '\xe2\x9a\x94 You attack and deal %s damage to a tree since no enemy was in sight' % dmg
        enemy.takedmg(dmg)
        if not self.enemy.alive():
            self.enemy = None
            exp = (1 + enemy.lvl)
            self.exp += exp
            gold = randint(2, 3 + enemy.lvl)
            self.gold += gold
            if self.exp >= self.level * 10:
                self.level  += 1
                self.maxhp  += 2
                self.maxdmg += 1
                self.exp    -= randint(1, self.level * 10)
                return '\xe2\x9a\x94 You strike the killing blow of %s damage to the %s which dies \xe2\x9a\x94 \n \xf0\x9f\x92\xb0 Searching the body you looted %s Gold\n :up: Congratz you are now Lvl.%s' % (dmg, enemy.name, gold, self.level)
            return '\xe2\x9a\x94 You strike the killing blow of %s damage to the %s which dies \xe2\x9a\x94 \n \xe2\x9c\xa8 You have gained %s exp \xe2\x9c\xa8 \n \xf0\x9f\x92\xb0 Searching the body you looted %s Gold' % (dmg, enemy.name, exp,gold)
        edmg = enemy.dodmg()
        self.hp -= edmg
        if self.hp <= 0:
            self.gameover()
            return '\xe2\x9a\x94 The %s struck you for %s damage killing you \xe2\x9a\x94' %(enemy.name, edmg)
        return '\xe2\x9a\x94 You swing your sword and deal %s damage to the %s which now has %s hp left\n \xe2\x9a\x94 The fierce %s countered with a %s damage attack leaving you with %s hp left' % (dmg, enemy.name, self.enemy.hp, enemy.name, edmg, self.hp)

    def walk(self):
        if self.enemy:
            return 'You have no time to loot, the %s gets in the way' % (self.enemy.name,)
        self.progress += 1
        if self.progress == 10:
            self.hp = self.maxhp
            postimg(self.chan, townpic, 'You did it! you finally reached the next town. \n As with every other town you only notice a shop and blacksmith to be of use\n The shop sells potions for 10\n The blacksmith upgrades for 15')
            return
        elif self.progress == 11:
            self.progress -= 11
            return 'You continue your adventure and walk out of town, by the time you look back its too far to return'
        elif self.hp < self.maxhp and randint(0, 1):
            rnd2 = randint(1, self.maxhp - self.hp)
            self.hp += rnd2
            self.cavloot += 1
            return 'While you travel towards the next town you decide to take a rest \n You regain %s of %s hp\n As you linger around you notice a cave nearby\n Do you loot it?' % (self.hp, self.maxhp)
        else:
            self.enemy = Enemy.new(self.level)
            postimg(self.chan, enemies[self.enemy.name], ' at a steady pace you cross paths with a %s' % self.enemy)
            return

    def loot(self):
        if self.enemy:
            return 'You have no time to loot, the %s gets in the way' % (self.enemy.name,)
        elif not self.cavloot:
            return 'You do not see any caves near you to loot'
        else:
            self.gold   += randint(0, 2)
            self.potion += randint(0, 2)
            dmg          = randint(0, 3)
            self.hp     -= dmg
            self.cavloot -= 1
            if self.hp <= 0:
                self.gameover()
                return 'You cut yourself in the cave for %s damage and died' % dmg
            return 'As you venture deep within the cave you managed to find\n \xf0\x9f\x92\xb0 %s Gold \n \xf0\x9f\x92\x9d %s Potion\n As you climb back out you cut your self for %s damage\n You now have %s hp' % (self.gold, self.potion, dmg, self.hp)

    def heal(self):
        if self.hp < self.maxhp:
            if self.potion > 0:
                heal = 5
                self.hp += heal
                self.potion -=1
                return ' \xf0\x9f\x92\x9e Your potion healed 5 hp, you now have %s hp !'  % (self.hp)
            return 'You have no potions left'
        return 'You are already at full hp'

    def buy(self):
        if self.progress != 10:
            return 'You are not at a shop to buy potions'
        elif self.gold < 15:
            return 'Come back later until you have enough you hobo.'
        else:
            self.potion += 5
            self.gold   -= 15
            return '\xf0\x9f\x9b\x92 You bought 5 potions from the shop keeper'

    def upgrade(self):
        if self.progress != 10:
            return 'You are not at a blacksmith to upgrade'
        elif self.gold < 15:
            return 'Come back later until you have enough you hobo.'
        else:
            self.maxdmg += 1
            self.gold   -= 15
            return '\xe2\x9a\x92 The blacksmith sharpened your sword gaining +1 dmg'

    def flee(self):
        if not self.enemy:
            return 'You fled from nothing and fell flat on your face'
        enemy = self.enemy
        edmg = enemy.dodmg()
        self.hp -= edmg
        if self.hp <= 0:
            self.gameover()
            return 'The %s gave chase and tackled you for %s damage then killed you' % (enemy.name, edmg)
        self.enemy = None
        return 'The %s managed to get one last swing of %s damage while you fled\nYou now have %s hp left' % (enemy.name,edmg, self.hp)

    def status(self):
        return tilde(block(attr.asdict(self)))

@attr.s
class Enemy(object):
    name = attr.ib()
    hp   = attr.ib()
    atk  = attr.ib()
    wep  = attr.ib()
    lvl  = attr.ib()

    @staticmethod
    def new(lvl):
        mlvl = randint(abs(lvl - 4) + 1, lvl + 5)
        return Enemy(name=choice(enemies.keys()),
                     hp=randint(abs(mlvl - 4) + 1, mlvl + 5),
                     atk=randint(abs(mlvl - 4) + 1, mlvl + 5),
                     wep=choice(weapons),
                     lvl=mlvl)

    def dodmg(self):
        return randint(0, self.atk)
    def takedmg(self, dmg):
        self.hp -= dmg
        return self.alive()
    def alive(self):
        return self.hp > 0
    def __str__(self):
        return 'lvl. %s %s wielding a %s with %s hp' % (self.lvl, self.name, self.wep, self.hp)


#\xe2\x99\xa5 \xf0\x9f\x8e\xb2  \xf0\x9f\x8e\x81  \xf0\x9f\x92\x94

sessions = {}

def getsession(user, chan):
    global sessions
    n = 0
    s = sessions.get(user)
    if not s:
        s = Game()
        sessions[user] = s
        n = 1
    s.user = user
    s.chan = chan
    return s, n


subcommands = dict(
    walk = 'walk',
    atk  = 'fight',
    flee = 'flee',
    stat = 'status',
    heal = 'heal',
    buy  = 'buy',
    upg  = 'upgrade',
    loot = 'loot',
    )

def handle(server, chan, user, mid, msg):
    if msg[0] != '.': return
    if chan != gameroom: return
    if ' ' not in msg:
        return 'Available subcommands: ' + ', '.join(subcommands.keys())
    cmd, sub = msg.split(' ', 1)
    if cmd != '.g': return
    if sub in subcommands:
        g, n = getsession(user, chan)
        p = getattr(g, subcommands[sub])()
        if n:
            return 'Session started' + ('\n' + p if p else '')
        return p
    elif sub == 'top':
        v = sorted(sessions.iteritems(), key=lambda x:x[1].maxhp, reverse=1)
        d = []
        for key, value in v:
            if value.level == 1: continue
            d.append('%s %s' % (key, value.level))
        return tilde('\n'.join(d))
    elif user not in (243306235351269386, 236951005529374722): return
    elif sub == 'dump':
        return tilde(pprint.pformat(sessions), 'python')
    elif sub == 'off':
        exit(repr(sessions))
    else:
        return 'Not a valid subcommand'


gameroom = 247480496043327489

enemies = {}
for e in 'orc knight witch discork snek'.split(' '):
    with open('images/%s.png' % e, 'rb') as f:
        enemies[e] = f.read()


with open('images/location.png', 'rb') as f:
    townpic = f.read()

weapons = 'club staff sword flail hammer axe'.split(' ')

# User code above

token = 'Bot ' + tokens['bot']

def block(d):
    out = []
    keys = d.keys()
    keys.sort()
    longest = len(max(keys, key=len))
    for k in keys:
        out.append('%s %s' % (k.ljust(longest), d[k]))
    return '\n'.join(out)

def tilde(text, type=''):
    return '```%s\n%s\n```' % (type, text)

def postimg(channel, imagedata, message=None):
    files   = dict(file=('image.png', imagedata))
    params  = dict()
    if message is not None:
            params['content'] = message
    headers = dict(Authorization=token)
    r = requests.post('%s/channels/%s/messages' % (apibase, channel),
                  files=files, data=params, headers=headers)
    return r.json()

def sendmsg(chan, msg):
    r.publish('discord.in.c.%s' % (chan), msg)

r = redis.Redis()
p = r.pubsub()
p.psubscribe('discord.out.*')

sendmsg(gameroom, 'Started')

for a in p.listen():
    if a['type'] != 'pmessage': continue
    c = a['channel'].split('.', 5)
    if len(c) != 6: continue
    if not a['data']: continue
    serv, chan, user, msgi = map(int, c[2:])
    try:
        reply = handle(serv, chan, user, msgi, a['data'])
        if reply:
            sendmsg(chan, str(reply))
    except RetErr as e:
        sendmsg(chan, str(e))
    except StandardError as e:
        traceback.print_exc(e)
sendmsg(chan, tilde(traceback.format_exc(e), 'python'))