# DropGameWeb

DropGameWeb は、Python と pygame で実装されたスイカ（Suika）ゲームのようなボールが落ちるパズルゲームです。同じ種類のワンちゃんを重ねて合体させ、スコアを競います。

## 特徴
- **純粋な pygame**: 物理エンジンを使わず、自前で物理シミュレーションを実装。
- **Web対応**: pygbag を使用して Python コードを WebAssembly (WASM) に変換。ブラウザで直接プレイ可能。
- **リアルタイム物理**: 重力、衝突、摩擦をシミュレートし、リアルなボール挙動を実現。

## 遊び方
- マウスでドロップ位置を調整し、クリックでワンちゃんを落とす。
- 同じレベルのワンちゃんが接触すると合体して次のレベルに進化。
- ワンちゃんが上部の赤いラインを超えるとゲームオーバー。
- Rキーでリセット。

## 技術詳細
- **pygbag**: Python コードを HTML5/WebGL/WebAssembly に変換。`python3 -m pygbag .` で `build/web` フォルダに以下のファイルが生成されます：
  - `index.html`: メインのHTMLページ。
  - `*.js`: JavaScriptファイル（pygbagランタイム）。
  - `*.wasm`: WebAssemblyファイル（Pythonコードのコンパイル結果）。
  - `web-cache/`: キャッシュファイル（パフォーマンス最適化用）。
  - `version.txt`: ビルドバージョン情報。
- **物理シミュレーション**: ボールの位置・速度を毎フレーム更新。衝突検出と応答を自前実装。
- **GitHub Pages**: `build/web` をデプロイして公開。ワークフロー（`.github/workflows/pages.yml`）で自動化。

## 公開URL
ゲームは以下のURLでプレイできます：  
[https://tkyasu999.github.io/DropGameWeb/](https://tkyasu999.github.io/DropGameWeb/)

## ローカル実行
1. Python と pygbag をインストール: `pip install pygbag`
2. ビルド: `python3 -m pygbag .`
3. ブラウザで `build/web/index.html` を開く。

## ライセンス
[LICENSE](LICENSE) を参照。
