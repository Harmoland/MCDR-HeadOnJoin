#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from threading import Lock

import regex
import yaml
from mcdreforged.api.all import *

lock = Lock()

save_folder: str
serve_folder: str
players_data: dict

color_map = {
    'black': RColor.black,
    'dark_blue': RColor.dark_blue,
    'dark_green': RColor.dark_green,
    'dark_aqua': RColor.dark_aqua,
    'dark_red': RColor.dark_red,
    'dark_purple': RColor.dark_purple,
    'gold': RColor.gold,
    'gray': RColor.gray,
    'dark_gray': RColor.dark_gray,
    'blue': RColor.blue,
    'green': RColor.green,
    'aqua': RColor.aqua,
    'red': RColor.red,
    'light_purple': RColor.light_purple,
    'yellow': RColor.yellow,
    'white': RColor.white,
}


@new_thread('HeadOnJoin_ReadSave')
def read_online_hour_from_save(player_uuid: str):
    with open(os.path.join(os.getcwd(), serve_folder, save_folder, 'stats', f'{player_uuid}.json')) as f:
        player_stats = f.read()
    player_stats = json.loads(player_stats)
    online_ticks = player_stats['stats']['minecraft:custom']['minecraft:play_time']
    online_total_sec = int(online_ticks / 20)
    online_minute, online_sec = divmod(online_total_sec, 60)
    online_hour = online_minute // 60
    return online_hour


@new_thread('HeadOnJoin_GiveHead')
def give_head(server: PluginServerInterface, player_uuid: str, player_name):
    if player_uuid not in players_data['players'].keys():
        players_data['players'][player_uuid] = 0
        server.save_config_simple(players_data, 'player.json')
        if players_data['firstJoinSendToEnderChest']:
            msg = players_data['message']['firstJoin']['toEnderChest']
            for i in regex.findall('&[0-9a-gk-r]', msg):
                msg = msg.replace(i, '§' + i[1])
            msg = msg.replace('<player_name>', player_name)
            server.tell(player_name, msg)
            server.execute(
                'item replace entity '
                + player_name
                + ' enderchest.0 with minecraft:player_head{SkullOwner:"'
                + player_name
                + '"}'
            )
        else:
            msg = players_data['message']['firstJoin']['toHand']
            for i in regex.findall('&[0-9a-gk-r]', msg):
                msg = msg.replace(i, '§' + i[1])
            msg = msg.replace('<player_name>', player_name)
            server.tell(player_name, msg)
            server.execute('give ' + player_name + ' minecraft:player_head{SkullOwner:"' + player_name + '"}')
    elif players_data['giveAnotherOneWhenPlay100h']:
        online_hour = read_online_hour_from_save(player_uuid).get_return_value(block=True)
        if online_hour >= 100 and players_data['players'][player_uuid] == 0:
            players_data['players'][player_uuid] += 1
            server.save_config_simple(players_data, 'player.json')
            msg = players_data['message']['100hJoin']
            for i in regex.findall('&[0-9a-gk-r]', msg):
                msg = msg.replace(i, '§' + i[1])
            server.tell(player_name, msg)
            server.execute('give ' + player_name + ' minecraft:player_head{SkullOwner:"' + player_name + '"}')


def on_info(server: PluginServerInterface, info: Info):
    re = regex.match(
        r'(UUID\ of\ player\ )(\S+)(\ is\ )([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', info.content
    )
    if not re:
        return
    player_name = re.group(2)
    player_uuid = re.group(4)
    give_head(server, player_uuid, player_name).join()


def on_load(server: PluginServerInterface, prev):
    global save_folder, serve_folder, players_data
    default_config = {
        'message': {
            'firstJoin': {
                'toEnderChest': 'Hello, &c<player_name>!\\n&b看起来你是第一次加入服务器，那就送你一个头吧，已经放到你的末影箱里了，要好好珍惜噢',
                'toHand': 'Hello, &c<player_name>!\\n&b看起来你是第一次加入服务器，送你一个头吧，要好好珍惜噢',
            },
            '100hJoin': '&9wow，&6今天是你在服务器游玩的第100个小时噢，送你一个头吧，要好好珍惜噢',
        },
        'firstJoinSendToEnderChest': True,
        'giveAnotherOneWhenPlay100h': True,
        'players': {},
    }
    players_data = server.load_config_simple('player.json', default_config)
    with open(os.path.join(os.getcwd(), 'config.yml'), 'r', encoding='utf-8') as f:
        mcdr_config = f.read()
    mcdr_config = yaml.load(mcdr_config, Loader=yaml.FullLoader)
    serve_folder = mcdr_config['working_directory']
    with open(os.path.join(os.getcwd(), serve_folder, 'server.properties')) as f:
        server_properties = f.read()
    re_result = regex.search(r'(level-name=)(\S+)', server_properties)
    if not re_result:
        pass
    save_folder = re_result.group(2)
