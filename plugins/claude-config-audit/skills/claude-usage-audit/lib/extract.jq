select(.timestamp != null and .timestamp >= $since)
| . as $r
| if .type=="attachment" and (.attachment.hookName != null) then
    {k:"hook", ev:.attachment.hookName, cmd:(.attachment.command//""), st:(.attachment.type//""),
     out:((.attachment.stdout//"")|length), ts:.timestamp, sid:(.sessionId//"")}
  elif .type=="assistant" then
    (.message.content[]? | select(.type=="tool_use")
      | if .name=="Skill" then {k:"skill", name:(.input.skill//"?"), ts:$r.timestamp, sid:($r.sessionId//"")}
        elif (.name=="Agent" or .name=="Task") then {k:"agent", name:(.input.subagent_type//"(none)"), ts:$r.timestamp, sid:($r.sessionId//"")}
        else empty end)
  elif .type=="user" then
    (( .message.content | if type=="string" then . else (map(select(.type=="text")|.text)|join("\n")) end ) as $t
     | if ($t|test("<command-name>")) then {k:"cmd", name:($t|capture("<command-name>(?<n>[^<]*)</command-name>").n), ts:$r.timestamp, sid:($r.sessionId//"")} else empty end)
  else empty end
