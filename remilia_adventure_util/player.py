import re
from datetime import datetime
from random import randint, choice
from time import time
from typing import Union

from remilia_adventure_util.talents import Talents, Talent

NOT_STARTED = 'NOT STARTED'
IN_PROGRESS = 'IN PROGRESS'
CHOICE = 'CHOICE'
GAME_OVER = 'GAME OVER'

GLOBAL_LUCK_CAP = 15
GLOBAL_HEALTH_CAP = 100
GLOBAL_ATTACK_CAP = 50

talents = Talents(True)


# Talent
# TODO：添加成就14
# TODO：添加特殊处理给12,13,19,49,42,59,60,71,74,76,77
# TODO: 添加特殊事件给23,32,54,55,56,57

class Player:
    def __init__(self, uid, is_debug=False):
        self.uid = str(uid)
        self.game_status = NOT_STARTED  # 游戏进行情况
        self.environment = None  # 探险活动

        self.current_choice = None  # 目前选择
        self.current_room = None  # 目前位置实体

        self.total_played = 0  # 玩了几次了
        self.third_wall_ending = 0  # 拿到10次后有惊喜？
        self.all_steps = 0  # 生涯经过房间
        self.current_step = 0  # 本次游戏经过房间
        self.all_death = 0  # 生涯死亡次数
        self.play_time = 0  # 生涯游玩次数

        self.base_luck = randint(0, 3)  # 幸运影响是否会更容易拿到好的道具或正面效果房间和buff
        self.base_health = randint(20, 50)  # 玩家血量base数值
        self.base_attack = randint(20, 30)  # 玩家永久伤害
        self.money = 0

        self.current_attack = self.base_attack  # 玩家临时伤害
        self.current_luck = self.base_luck  # 临时幸运
        self.current_health = self.base_health  # 临时血量
        self.current_true_damage_ratio = 0.0
        self.current_true_damage_literal = 0
        self.current_killed_monster = 0

        self.total_killed_monster = 0
        self.current_life = 1

        self.last_updated_time = time()

        self.achievement_list = set()
        self.event_id_set = set()

        self.talent_set = set()
        self.is_all_buff_talent = False
        self.is_all_debuff_talent = False

        self.item_set = set()
        self.player_talent = []
        self.update_check = []

        self.is_debug = is_debug

    def reset_player(self):
        self.current_true_damage_ratio = 0.0
        self.current_true_damage_literal = 0
        self.current_choice = None
        self.current_life = 1
        self.total_played += 1
        self.current_luck = self.base_luck
        self.current_attack = self.base_attack
        self.current_health = self.base_health
        self.current_step = 0
        self.current_killed_monster = 0

        self.achievement_list.clear()
        self.event_id_set.clear()
        self.talent_set.clear()
        self.item_set.clear()
        self.player_talent.clear()

        self.game_status = NOT_STARTED
        self.environment = None

    def _random_talent_helper(self, talent, exclude_talent, return_talent):
        while talent.preq_luck > self.base_luck or \
                talent.preq_attack > self.base_attack or \
                talent.preq_health > self.base_health or \
                talent.preq_death > self.all_death or \
                talent.preq_playtime > self.play_time:
            talent = talents.get_random_talent()

        while talent.talent_id in exclude_talent or talent in return_talent:
            talent = talents.get_random_talent()

        return talent

    def get_random_talents(self):
        return_talent = []
        added_talent = set()
        exclude_talent = set()

        for _ in range(5):
            talent = talents.get_random_talent()
            if talent.talent_id in added_talent:
                continue

            if '72' in added_talent and '73' not in added_talent:
                return_talent.append(talents.get_talents_by_id('73'))
                added_talent.add('73')

            if '73' in added_talent and '72' not in added_talent:
                return_talent.append(talents.get_talents_by_id('72'))
                added_talent.add('72')

            talent = self._random_talent_helper(talent, exclude_talent, return_talent)

            if talent.exclude_talent is not None:
                for e in talent.exclude_talent:
                    exclude_talent.add(e)

            need_new_talent = True
            if talent.need_achievement is not None:
                while need_new_talent:
                    for achievement in talent.need_achievement:
                        if achievement not in self.achievement_list:
                            talent = talents.get_random_talent()
                            talent = self._random_talent_helper(talent, exclude_talent, return_talent)
                            break
                    else:
                        need_new_talent = False
                        return_talent.append(talent)
                        added_talent.add(talent.talent_id)

            else:
                return_talent.append(talent)
                added_talent.add(talent.talent_id)

        return return_talent

    def choose_talent(self, query, given_talent):
        query = re.sub(r'，+', ',', query)
        query = re.sub(r'[^\d,]+', '', query)
        query_list = query.split(',')

        for talent in query_list:
            if talent not in given_talent:
                return False, '我可没给你这个天赋让你选哦'

            talent = talents.get_talents_by_id(talent)
            if talent is None:
                return False, '什么jb玩意……'

            # 如果不需要动态更改则直接应用改变
            if talent.activate_need is None:
                self.set_user_data_by_talent_passive(talent)
                self.change_user_data_by_talent_passive(talent)
            else:
                updates = talent.activate_need
                for update in updates:
                    update['title'] = talent.title
                    self.update_check.append(update)

            self.talent_set.add(talent.talent_id)

        return True, 'Success!'

    def change_user_data_by_talent_passive(self, talent: Talent):
        self.current_attack += talent.change_attack
        self.current_luck += talent.change_luck if self.current_luck > 0 else 0  # 处理“倒霉催的”talent
        self.current_health += talent.change_health
        self.current_life += talent.change_life if self.current_life != 0 else 0  # 处理“献祭”talent

    def set_user_data_by_talent_passive(self, talent: Talent):
        if talent.set_health is not None and talent.set_health < self.current_health:
            self.current_health = talent.set_health

        if talent.set_luck is not None and talent.set_luck < self.current_luck:
            self.current_luck = talent.set_luck

        if talent.set_attack is not None and talent.set_attack < self.current_attack:
            self.current_attack = talent.set_attack

        if talent.set_step is not None and talent.set_step < self.current_step:
            self.current_step = talent.set_step


# HELPER PARSER FOR ACTIVATES
def decider_value_parser(decider: str, player: Player):
    return {
        'health': lambda: player.current_health,
        'step': lambda: player.current_step,
        'attack': lambda: player.current_attack,
        'life': lambda: player.current_life,
        'luck': lambda: player.current_luck,
        'buff_condition': lambda: player.is_all_buff_talent,
        'time_hour': lambda: datetime.now().hour,
        'time_minute': lambda: datetime.now().minute,
        'time_second': lambda: datetime.now().second
    }.get(decider, -999)()


def condition_compare(expr_condition: str, decider: str, player: Player, expected_value: Union[int, float, str]):
    p_value = decider_value_parser(decider, player)

    return {
        '>': lambda: p_value > expected_value,
        '>=': lambda: p_value >= expected_value,
        '==': lambda: p_value == expected_value,
        '<': lambda: p_value < expected_value,
        '<=': lambda: p_value <= expected_value,
        '%': lambda: p_value % expected_value == 0
    }.get(expr_condition, False)()


def _parse_influence(influence: str, player: Player, action: str, var: Union[int, float]):
    if influence == 'health':
        if action == 'change':
            player.current_health += var
        else:
            player.current_health = var
    elif influence == 'attack':
        if action == 'change':
            player.current_attack += var
        else:
            player.current_attack = var
    elif influence == 'life':
        if action == 'change':
            player.current_life += var
        else:
            player.current_life = var
    elif influence == 'luck':
        if action == 'change':
            player.current_luck += var
        else:
            player.current_luck = var


def parse_talent_activate_condition(talent: Talent, player: Player):
    condition = talent.activate_need
    for cond in condition:
        expr_condition = cond['condition']
        decider = cond['decider']
        decider_value = cond[decider]
        payloads = cond['result']

        if condition_compare(expr_condition, decider, player, decider_value):
            for payload in payloads:
                action = payload['action']
                prop = payload['prop']
                influence = payload['influence']

                if action in ('change', 'set'):
                    _parse_influence(influence, player, action, talent.data[action][prop])
                else:
                    action = action.split('[!]')
                    action_var = action[1]
                    _parse_influence(influence, player, action_var, choice(talent.data[action][prop]))


if __name__ == '__main__':
    # debug testing
    talenta = Talents()
    playera = Player(634915227)
    talent_dkfx = talenta.get_talents_by_id('20')
    playera.current_step = 1
    parse_talent_activate_condition(talent_dkfx, playera)
    print()
