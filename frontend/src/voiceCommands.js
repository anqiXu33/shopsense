/**
 * Turn a spoken transcript into a navigation command, so the store can be
 * used by voice alone. Anything that is not a command is treated as a search
 * need or a question by the page that heard it.
 *
 * Returns one of:
 *   { type: 'open', n }   "打开第二款" / "第2款" / "open number two"
 *   { type: 'back' }      "返回" / "go back"
 *   { type: 'repeat' }    "重复要点" / "再说一遍" / "repeat highlights"
 *   { type: 'stop' }      "停止" / "stop"
 *   { type: 'describe' }  "描述外观" / "长什么样" / "what does it look like"
 *   null                  not a command
 */

const ZH_DIGITS = { 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10 }
const EN_NUMBERS = {
  one: 1, first: 1, two: 2, second: 2, to: 2, too: 2, three: 3, third: 3,
  four: 4, fourth: 4, for: 4, five: 5, fifth: 5,
}

export function parseCommand(transcript) {
  const text = transcript.trim().toLowerCase().replace(/[。.!！?？,，]/g, '')

  const zhOpen = text.match(/^(?:打开|查看|看看|看)?第\s*([0-9一二两三四五六七八九十]+)\s*[款个双]?$/)
  if (zhOpen) {
    const raw = zhOpen[1]
    return { type: 'open', n: ZH_DIGITS[raw] ?? parseInt(raw, 10) }
  }
  const enOpen = text.match(/^(?:open|show)(?: the)?(?: number| item| product)? (\w+)(?: one)?$/)
  if (enOpen) {
    const n = EN_NUMBERS[enOpen[1]] ?? parseInt(enOpen[1], 10)
    if (Number.isInteger(n)) return { type: 'open', n }
  }
  if (/^(返回|回去|go back|back)$/.test(text)) return { type: 'back' }
  if (/^(重复要点|重复|再说一遍|repeat highlights|repeat)$/.test(text)) return { type: 'repeat' }
  if (/^(停止|停|别说了|stop)$/.test(text)) return { type: 'stop' }
  if (/^(描述外观|外观|长什么样|长什么样子|describe it|describe the shoe|describe appearance|what does it look like)$/.test(text)) {
    return { type: 'describe' }
  }
  return null
}
