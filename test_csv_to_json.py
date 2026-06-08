#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
csv_to_case1_json.pyのユニットテスト
"""

import csv
import json
import tempfile
import unittest
from pathlib import Path
import sys
import os

# テスト対象のモジュールをインポート
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csv_to_case1_json import parse_value, parse_csv_with_units, convert_csv_to_case1_json


class TestParseValue(unittest.TestCase):
    """parse_value関数のテスト"""

    def test_parse_numbers(self):
        """数値パースのテスト"""
        self.assertEqual(parse_value('13.5'), 13.5)
        self.assertEqual(parse_value('550'), 550)
        self.assertEqual(parse_value('(12.7)'), 12.7)

    def test_parse_special_values(self):
        """特殊値のテスト"""
        self.assertIsNone(parse_value('-'))
        self.assertIsNone(parse_value('Tr'))
        self.assertIsNone(parse_value('(Tr)'))
        self.assertIsNone(parse_value(''))

    def test_parse_strings(self):
        """文字列値のテスト"""
        self.assertEqual(parse_value('備考テキスト'), '備考テキスト')




class TestCSVWithUnits(unittest.TestCase):
    """CSV単位行読み込みのテスト"""

    def setUp(self):
        """テスト用CSVファイルの作成"""
        self.test_csv_content = """食品群,食品番号,索引番号,食品名,水分,たんぱく質,イソロイシン,備考
,,,成分識別子,WATER,PROT-,ILE,
,,,単位,g/100 g,g/100 g,mg/100 g,
01,01001,1,アマランサス　玄穀,13.5,12.7,550,米国成分表より推計
"""
        # 一時ファイルを作成
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig',
                                                      suffix='.csv', delete=False)
        self.temp_file.write(self.test_csv_content)
        self.temp_file.close()

        # 出力ディレクトリ
        self.output_dir = Path(self.temp_file.name).parent / 'test_output'

    def tearDown(self):
        """テンポラリファイルの削除"""
        Path(self.temp_file.name).unlink()
        # 出力ディレクトリも削除
        if self.output_dir.exists():
            for file in self.output_dir.glob('*.json'):
                file.unlink()
            self.output_dir.rmdir()

    def test_parse_csv_with_units(self):
        """CSVから単位マップを作成できるか"""
        # ここで新しい実装をテストする予定
        # TODO: parse_csv_with_units関数を実装後にテスト追加
        pass

    def test_convert_csv_basic(self):
        """基本的なCSV変換テスト"""
        convert_csv_to_case1_json(self.temp_file.name, self.output_dir)

        # 出力ファイルの確認
        output_files = list(self.output_dir.glob('*.json'))
        self.assertEqual(len(output_files), 1)

        # JSONファイルの内容を確認
        with open(output_files[0], 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertEqual(data['食品名'], 'アマランサス　玄穀')

        # 基本情報の確認
        basic_info_dict = {item['項目']: item['値'] for item in data['基本情報']}
        self.assertEqual(basic_info_dict['食品群'], '01')
        self.assertEqual(basic_info_dict['食品番号'], '01001')
        self.assertEqual(basic_info_dict['備考'], '米国成分表より推計')

        # 栄養成分の確認
        nutrients_dict = {item['名前']: item for item in data['栄養成分']}

        # 水分
        self.assertEqual(nutrients_dict['水分']['含有量'], 13.5)
        self.assertEqual(nutrients_dict['水分']['単位'], 'g/100g')

        # たんぱく質
        self.assertEqual(nutrients_dict['たんぱく質']['含有量'], 12.7)
        self.assertEqual(nutrients_dict['たんぱく質']['単位'], 'g/100g')

        # イソロイシン
        self.assertEqual(nutrients_dict['イソロイシン']['含有量'], 550)
        self.assertEqual(nutrients_dict['イソロイシン']['単位'], 'mg/100g')


if __name__ == '__main__':
    unittest.main()