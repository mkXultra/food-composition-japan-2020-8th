#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import sys
from pathlib import Path

def parse_value(value_str):
    """値をパースして文字列のまま返す（カッコも保持）"""
    if not value_str or value_str == '-':
        return None

    # 空白を除去するが、カッコは保持
    value_str = value_str.strip()

    # Trや(Tr)はそのまま返す（微量の表記）
    # その他の値もすべて文字列として返す
    return value_str

def parse_csv_with_units(csv_file_path):
    """CSVファイルを読み込み、ヘッダーと単位マップを作成"""

    # CSVファイルを読み込み（カラム内の改行も正しく処理）
    with open(csv_file_path, 'r', encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))

    # 最低4行必要（ヘッダー、成分識別子、単位、データ）
    if len(rows) < 4:
        raise ValueError("CSVファイルのフォーマットが不正です")

    # 1行目: ヘッダー（栄養素名）
    headers = [h.replace('\n', '').strip() for h in rows[0]]  # 改行を除去

    # 2行目: 成分識別子（スキップ）
    # 3行目: 単位
    units = [u.strip() for u in rows[2]]

    # ヘッダーと単位のマップを作成
    unit_map = {}
    for i, header in enumerate(headers):
        if i < len(units) and units[i] and header:
            # "g/100 g" → "g/100g" に正規化
            unit = units[i].replace(' ', '')
            unit_map[header] = unit

    return headers, unit_map, rows[3:]  # 4行目以降がデータ（リスト形式）

def convert_csv_to_case1_json(csv_file_path, output_dir=None):
    """CSVファイルを案1のJSON構造に変換"""

    # ヘッダーと単位マップを取得
    headers, unit_map, data_lines = parse_csv_with_units(csv_file_path)
    
    # 基本情報と栄養成分を分類するためのキー
    basic_info_keys = ['食品群', '食品番号', '索引番号', '食品名', '備考']
    skip_keys = ['成分識別子']  # スキップするカラム
    
    # 出力ディレクトリの設定
    if output_dir is None:
        output_dir = Path(csv_file_path).parent / 'case1_json'
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(exist_ok=True)

    # データ行を処理
    for row_data in data_lines:
        # 空行をスキップ（すべての要素が空の場合）
        if not any(row_data):
            continue

        # ヘッダーと値を辞書に変換
        row = dict(zip(headers, row_data))

        # 食品名が空の場合はスキップ
        if not row.get('食品名') or row.get('食品名') == '-':
            continue
        
        # 基本データ構造
        food_data = {
            "食品名": row.get('食品名', '').replace('\n', ''),
            "基本情報": [],
            "栄養成分": []
        }
        
        # 各カラムを処理
        for header in headers:
            # スキップするカラム
            if header in skip_keys or not header:
                continue
            
            # 食品名は既に設定済み
            if header == '食品名':
                continue
            
            value_str = row.get(header, '')
            
            # 基本情報の処理
            if header in basic_info_keys:
                if header == '備考' and value_str and value_str != '-':
                    food_data["基本情報"].append({
                        "項目": header,
                        "値": value_str
                    })
                elif header != '備考' and value_str:
                    food_data["基本情報"].append({
                        "項目": header,
                        "値": value_str
                    })
            else:
                # 栄養成分の処理
                value = parse_value(value_str)
                if value is not None:
                    nutrient_data = {
                        "名前": header.replace('\n', ''),  # 改行を削除
                        "含有量": value
                    }
                    # 単位マップから単位を取得
                    unit = unit_map.get(header, "")
                    if unit:
                        nutrient_data["単位"] = unit

                    food_data["栄養成分"].append(nutrient_data)
        
        # 空の配列を削除
        if not food_data["基本情報"]:
            del food_data["基本情報"]
        if not food_data["栄養成分"]:
            del food_data["栄養成分"]
        
        # JSONファイルとして保存
        food_number = row.get('食品番号', 'unknown')
        safe_name = food_data['食品名'].replace('　', '_').replace(' ', '_').replace('/', '_')
        output_file = output_dir / f"{food_number}_{safe_name}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(food_data, f, ensure_ascii=False, indent=2)
        
        print(f"Created: {output_file}")

    # デバッグ: 単位マップの一部を出力
    print(f"\n単位マップから読み込んだ単位の例:")
    sample_keys = ['水分', 'たんぱく質', 'イソロイシン', 'ロイシン', 'カリウム']
    for key in sample_keys:
        if key in unit_map:
            print(f"  {key}: {unit_map[key]}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python csv_to_case1_json.py <csv_file_path> [output_dir]")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_csv_to_case1_json(csv_file, output_dir)
    print("Conversion completed!")