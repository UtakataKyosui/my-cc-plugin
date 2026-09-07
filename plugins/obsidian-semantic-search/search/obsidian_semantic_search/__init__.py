"""Obsidian Vault のローカル意味検索（セマンティック検索）エンジン。

埋め込みモデル（sentence-transformers）でノートをベクトル化し、numpy の
総当たりコサイン類似度で関連ノートを返す。LLM には依存せず、Vault 内容を
外部に送信しない。CLI から `index` / `query` / `status` を呼んで使う。
"""

__version__ = "0.1.0"
