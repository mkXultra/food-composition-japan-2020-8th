#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import sys
from pathlib import Path

def parse_value(value_str):
    """値をパースして数値か文字列を返す"""
    if not value_str or value_str == '-' or value_str == 'Tr' or value_str == '(Tr)':
        return None
    
    # カッコを除去して数値を抽出
    value_str = value_str.replace('(', '').replace(')', '').strip()
    
    # 数値変換を試みる
    try:
        # 小数点を含む場合
        if '.' in value_str:
            return float(value_str)
        else:
            return int(value_str)
    except ValueError:
        return value_str

def clean_amino_acid_name(name):
    """アミノ酸名をクリーンにする（改行と不要な前置詞を削除）"""
    # 改行を削除
    name = name.replace('\n', '')
    # 前置詞を削除
    if name.startswith('含硫アミノ酸；'):
        # 合計は除外
        if name == '含硫アミノ酸；合計':
            return None
        name = name.replace('含硫アミノ酸；', '')
    elif name.startswith('芳香族アミノ酸；'):
        # 合計は除外
        if name == '芳香族アミノ酸；合計':
            return None
        name = name.replace('芳香族アミノ酸；', '')
    # その他の改行を含む名前を処理
    name = name.replace('リシン（リジン）', 'リシン（リジン）')
    name = name.replace('トレオニン（スレオニン）', 'トレオニン（スレオニン）')
    
    return name

def is_amino_acid(header):
    """ヘッダーがアミノ酸かどうかを判定"""
    amino_acids = [
        'イソロイシン', 'ロイシン', 'リシン', 'リジン', 'メチオニン', 'シスチン',
        'フェニルアラニン', 'チロシン', 'トレオニン', 'スレオニン', 'トリプトファン',
        'バリン', 'ヒスチジン', 'アルギニン', 'アラニン', 'アスパラギン酸',
        'グルタミン酸', 'グリシン', 'プロリン', 'セリン', 'ヒドロキシプロリン'
    ]
    
    # ヘッダーに含まれるアミノ酸名をチェック
    for amino in amino_acids:
        if amino in header:
            return True
    return False

def is_nutrient(header):
    """ヘッダーが主要栄養成分かどうかを判定"""
    nutrients = ['水分', 'たんぱく質', '脂質', '炭水化物', 'エネルギー']
    
    # アミノ酸組成によるたんぱく質も栄養成分に含める
    if 'アミノ酸組成によるたんぱく質' in header:
        return True
    
    for nutrient in nutrients:
        if nutrient in header and not is_amino_acid(header):
            return True
    return False

def convert_csv_to_case1_json_v2(csv_file_path, output_dir=None):
    """CSVファイルを元の案1のJSON構造（カテゴリ分け）に変換"""
    
    # CSVファイルを読み込み（エンコーディングを指定）
    with open(csv_file_path, 'r', encoding='utf-8-sig', newline='') as f:
        # 改行文字の問題を回避
        content = f.read()
        # 改行文字を正規化
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
    # 文字列IOを使ってCSVを読み込み
    import io
    csv_file = io.StringIO(content)
    reader = csv.DictReader(csv_file)
    
    # ヘッダーを取得
    headers = reader.fieldnames
    
    # 基本情報と栄養成分を分類するためのキー
    basic_info_keys = ['食品群', '食品番号', '索引番号', '食品名', '備考']
    skip_keys = ['成分識別子', 'アンモニア', '剰余アンモニア']  # スキップするカラム
    
    # 出力ディレクトリの設定
    if output_dir is None:
        output_dir = Path(csv_file_path).parent / 'case1_json_v2'
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(exist_ok=True)
    
    # 各行を処理
    for row in reader:
        # 空行やヘッダー行をスキップ
        if not row.get('食品名') or row.get('食品名') == '食品名':
            continue
        
        # 基本データ構造
        food_data = {
            "食品名": row.get('食品名', ''),
            "基本情報": [],
            "栄養成分": [],
            "アミノ酸": []
        }
        
        # アミノ酸組成計の値を保存
        amino_acid_total = None
        
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
                value = parse_value(value_str)
                if value is not None:
                    # アミノ酸組成計は別扱い
                    if 'アミノ酸組成計' in header:
                        amino_acid_total = {
                            "含有量": value,
                            "単位": "mg/100g"
                        }
                    # 栄養成分（水分、たんぱく質など）
                    elif is_nutrient(header):
                        food_data["栄養成分"].append({
                            "名前": header.replace('\n', ''),
                            "含有量": value,
                            "単位": "g/100g"
                        })
                    # アミノ酸
                    elif is_amino_acid(header):
                        clean_name = clean_amino_acid_name(header)
                        if clean_name:  # 合計は除外されるのでNoneチェック
                            food_data["アミノ酸"].append({
                                "名前": clean_name,
                                "含有量": value,
                                "単位": "mg/100g"
                            })
        
        # アミノ酸組成計を追加
        if amino_acid_total:
            food_data["アミノ酸組成計"] = amino_acid_total
        
        # 空の配列を削除
        if not food_data["基本情報"]:
            del food_data["基本情報"]
        if not food_data["栄養成分"]:
            del food_data["栄養成分"]
        if not food_data["アミノ酸"]:
            del food_data["アミノ酸"]
        
        # JSONファイルとして保存
        food_number = row.get('食品番号', 'unknown')
        safe_name = food_data['食品名'].replace('　', '_').replace(' ', '_').replace('/', '_')
        output_file = output_dir / f"{food_number}_{safe_name}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(food_data, f, ensure_ascii=False, indent=2)
        
        print(f"Created: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python csv_to_case1_json_v2.py <csv_file_path> [output_dir]")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_csv_to_case1_json_v2(csv_file, output_dir)
    print("Conversion completed!")