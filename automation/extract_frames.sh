#!/bin/bash
# 영상에서 첫/중간/마지막 프레임 추출
# Usage: bash extract_frames.sh input.mp4 output_dir/

set -e

INPUT="$1"
OUTPUT_DIR="${2:-.}"

if [ -z "$INPUT" ]; then
    echo "Usage: bash extract_frames.sh <video_file> [output_dir]"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# 영상 길이 확인
DURATION=$(ffprobe -v quiet -print_format json -show_format "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['format']['duration'])")

# 타임스탬프 계산 (25%, 50%, 75% 지점)
T1=$(python3 -c "print(float($DURATION) * 0.05)")
T2=$(python3 -c "print(float($DURATION) * 0.50)")
T3=$(python3 -c "print(float($DURATION) * 0.95)")

# 프레임 추출
ffmpeg -y -ss "$T1" -i "$INPUT" -vframes 1 -q:v 2 "$OUTPUT_DIR/frame_first.png" 2>/dev/null
ffmpeg -y -ss "$T2" -i "$INPUT" -vframes 1 -q:v 2 "$OUTPUT_DIR/frame_mid.png" 2>/dev/null
ffmpeg -y -ss "$T3" -i "$INPUT" -vframes 1 -q:v 2 "$OUTPUT_DIR/frame_last.png" 2>/dev/null

echo "추출 완료:"
echo "  첫 프레임:    $OUTPUT_DIR/frame_first.png (t=${T1}s)"
echo "  중간 프레임:  $OUTPUT_DIR/frame_mid.png (t=${T2}s)"
echo "  마지막 프레임: $OUTPUT_DIR/frame_last.png (t=${T3}s)"
