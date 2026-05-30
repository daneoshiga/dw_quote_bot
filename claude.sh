  # dispatch one subagent per pending task
  todo.sh ls status:pending | while read line; do
    task_num=$(echo "$line" | awk '{print $1}')
    claude \
      --verbose \
      --print \
      --output-format stream-json \
      "Work on todo task $task_num using the todo-agent skill. Mark it done when complete. more context on docs/prd-game-state-machine.md"
      grep --line-buffered '^{' \
      tee "$tmpfile" \
      jq --unbuffered -rj "$stream_text"

  done
