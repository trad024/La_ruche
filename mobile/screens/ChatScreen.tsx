import { useState, useRef } from 'react'
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from 'react-native'
import { streamChat } from '../api/client'

interface Msg {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export default function ChatScreen() {
  const [messages, setMessages] = useState<Msg[]>([
    { id: '0', role: 'assistant', content: "Hello! I'm your WealthMesh advisor. How can I help?" },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const convId = useRef(Math.random().toString(36).slice(2))
  const listRef = useRef<FlatList>(null)

  async function send() {
    if (!input.trim() || loading) return
    const text = input.trim()
    setInput('')

    const userMsg: Msg = { id: Date.now().toString(), role: 'user', content: text }
    const assistantMsg: Msg = { id: (Date.now() + 1).toString(), role: 'assistant', content: '' }

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setLoading(true)

    try {
      let acc = ''
      for await (const token of streamChat(text, convId.current)) {
        acc += token
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { ...assistantMsg, content: acc }
          return updated
        })
      }
    } catch {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { ...assistantMsg, content: '[Error: Orchestrator unavailable]' }
        return updated
      })
    } finally {
      setLoading(false)
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100)
    }
  }

  return (
    <KeyboardAvoidingView
      style={s.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}
    >
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={m => m.id}
        contentContainerStyle={s.list}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
        renderItem={({ item }) => (
          <View style={[s.bubble, item.role === 'user' ? s.userBubble : s.botBubble]}>
            <Text style={[s.bubbleText, item.role === 'user' ? s.userText : s.botText]}>
              {item.content || (loading ? '...' : '')}
            </Text>
          </View>
        )}
      />

      <View style={s.inputRow}>
        <TextInput
          testID="chat-input"
          accessibilityLabel="chat-input"
          style={s.input}
          placeholder="Ask about your portfolio..."
          placeholderTextColor="#64748b"
          value={input}
          onChangeText={setInput}
          onSubmitEditing={send}
          editable={!loading}
          returnKeyType="send"
        />
        <TouchableOpacity
          testID="chat-send"
          accessibilityLabel="chat-send"
          style={[s.sendBtn, (loading || !input.trim()) && s.sendDisabled]}
          onPress={send}
        >
          <Text style={s.sendText}>→</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  )
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  list: { padding: 12, gap: 10 },
  bubble: { maxWidth: '80%', borderRadius: 14, paddingHorizontal: 12, paddingVertical: 8 },
  userBubble: { alignSelf: 'flex-end', backgroundColor: '#7c3aed' },
  botBubble: { alignSelf: 'flex-start', backgroundColor: '#1e293b', borderWidth: 1, borderColor: '#334155' },
  bubbleText: { fontSize: 14, lineHeight: 20 },
  userText: { color: '#fff' },
  botText: { color: '#cbd5e1' },
  inputRow: {
    flexDirection: 'row',
    gap: 8,
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: '#1e293b',
    backgroundColor: '#0f172a',
  },
  input: {
    flex: 1,
    backgroundColor: '#1e293b',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    color: '#fff',
    fontSize: 14,
    borderWidth: 1,
    borderColor: '#334155',
  },
  sendBtn: {
    backgroundColor: '#7c3aed',
    borderRadius: 12,
    width: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendDisabled: { opacity: 0.5 },
  sendText: { color: '#fff', fontSize: 18 },
})
