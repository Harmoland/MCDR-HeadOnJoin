#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from logging import Logger
from typing import Dict

import httpx
import regex
import yaml
from httpx import Response
from mcdreforged.api.decorator import new_thread
from mcdreforged.api.types import Info, PluginServerInterface

logger: Logger
players: Dict[str, str] = {}
save_folder: str
serve_folder: str
config: dict


@new_thread('HeadOnJoin_ReadSave')
def read_online_hour_from_save(server: PluginServerInterface, player_uuid: str, player_name: str) -> int:
    try:
        with open(os.path.join(os.getcwd(), serve_folder, save_folder, 'stats', f'{player_uuid}.json')) as f:
            player_stats = f.read()
    except FileNotFoundError:
        first_join_give_gead(server, player_uuid, player_name)
        return 0
    player_stats = json.loads(player_stats)
    online_ticks = player_stats['stats']['minecraft:custom']['minecraft:play_time']
    online_total_sec = int(online_ticks / 20)
    online_minute, online_sec = divmod(online_total_sec, 60)
    online_hour = online_minute // 60
    return online_hour


def first_join_give_gead(server: PluginServerInterface, player_uuid: str, player_name: str):
    config['players'][player_uuid] = 0
    server.save_config_simple(config, 'player.json')
    if config['sendToEnderChestWhenFirstJoin']:
        msg = config['message']['firstJoin']['toEnderChest']
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
        msg = config['message']['firstJoin']['toHand']
        for i in regex.findall('&[0-9a-gk-r]', msg):
            msg = msg.replace(i, '§' + i[1])
        msg = msg.replace('<player_name>', player_name)
        server.tell(player_name, msg)
        server.execute('give ' + player_name + ' minecraft:player_head{SkullOwner:"' + player_name + '"}')


@new_thread('HeadOnJoin_GiveHead')
def give_head(server: PluginServerInterface, player_uuid: str, player_name: str):
    if player_uuid not in config['players'].keys():
        first_join_give_gead(server, player_uuid, player_name)
    elif config['giveAnotherHeadWhenPlay100h']:
        online_hour: int = read_online_hour_from_save(server, player_uuid, player_name).get_return_value(block=True)
        if online_hour >= 100 and config['players'][player_uuid] == 0:
            config['players'][player_uuid] += 1
            server.save_config_simple(config, 'player.json')
            msg = config['message']['100hJoin']
            for i in regex.findall('&[0-9a-gk-r]', msg):
                msg = msg.replace(i, '§' + i[1])
            server.tell(player_name, msg)
            server.execute('give ' + player_name + ' minecraft:player_head{SkullOwner:"' + player_name + '"}')


@new_thread('HeadOnJoin_GetUUID')
def get_player_uuid(player_name: str) -> Response:
    res: Response = httpx.get(f'https://api.mojang.com/users/profiles/minecraft/{player_name}')
    return res


def on_info(server: PluginServerInterface, info: Info):
    if not info.is_from_server and not info.content.startswith('UUID of player'):
        return
    re = regex.match(
        r'(UUID\ of\ player\ )(\S+)(\ is\ )([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', info.content
    )
    if not re:
        return
    global players
    player_name = re.group(2)
    player_uuid = re.group(4)
    players[player_name] = player_uuid


def on_player_joined(server: PluginServerInterface, player_name: str, info: Info):
    global players
    for player in players.keys():
        if player_name == player:
            give_head(server, players[player_name], player_name).join()
            del players[player_name]
            return
    res: Response = get_player_uuid(player_name).get_return_value(block=True)
    if res.status_code == 200:
        give_head(server, res.json()['id'], player_name).join()
    elif res.status_code == 204:
        return
    else:
        server.tell(player_name, config['message']['apiError'])
        logger.error(f'无法获取玩家 {player_name} 的 UUID，因此无法给予头颅。Mojang API 返回状态码：{res.status_code}，返回内容：{res.content}')


def on_load(server: PluginServerInterface, prev):
    global logger, save_folder, serve_folder, config
    logger = server.logger
    default_config = {
        'message': {
            'firstJoin': {
                'toEnderChest': 'Hello, &c<player_name>!\n&b看起来你是第一次加入服务器，那就送你一个头吧，已经放到你的末影箱里了，要好好珍惜噢',
                'toHand': 'Hello, &c<player_name>!\n&b看起来你是第一次加入服务器，送你一个头吧，要好好珍惜噢',
            },
            '100hJoin': '&9wow，&6今天是你在服务器游玩的第100个小时噢，送你一个头吧，要好好珍惜噢',
            'apiError': '无法从 Mojang API 获取你的 UUID 因此无法给你发送头颅，请联系服务器管理员',
        },
        'sendToEnderChestWhenFirstJoin': True,
        'giveAnotherHeadWhenPlay100h': True,
        'players': {},
    }
    config = server.load_config_simple('player.json', default_config)
    with open(os.path.join(os.getcwd(), 'config.yml'), 'r', encoding='utf-8') as f:
        mcdr_config = f.read()
    mcdr_config = yaml.load(mcdr_config, Loader=yaml.FullLoader)
    serve_folder = mcdr_config['working_directory']
    with open(os.path.join(os.getcwd(), serve_folder, 'server.properties')) as f:
        server_properties = f.read()
    re = regex.search(r'(level-name=)(\S+)', server_properties)
    if re:
        save_folder = re.group(2)
    else:
        save_folder = 'world'
