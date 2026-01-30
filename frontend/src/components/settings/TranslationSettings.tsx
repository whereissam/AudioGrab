import { useState, useEffect } from 'react'
import { Loader2, Check, AlertCircle, Languages, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Language {
  code: string
  name: string
}

interface TranslateAvailability {
  available: boolean
  models: string[]
  ollama_url: string
  error?: string
}

const MODEL_SIZES = [
  { value: '4b', label: '4B', desc: '3.3GB - Fastest' },
  { value: '12b', label: '12B', desc: '8.1GB - Balanced' },
  { value: '27b', label: '27B', desc: '17GB - Best quality' },
]

export function TranslationSettings() {
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState(false)
  const [availability, setAvailability] = useState<TranslateAvailability | null>(null)
  const [languages, setLanguages] = useState<Language[]>([])
  const [selectedModel, setSelectedModel] = useState('4b')
  const [defaultTargetLang, setDefaultTargetLang] = useState('')
  const [testResult, setTestResult] = useState<{
    success: boolean
    error?: string
    translated?: string
  } | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [availRes, langRes] = await Promise.all([
        fetch('/api/translate/available'),
        fetch('/api/translate/languages'),
      ])

      if (availRes.ok) {
        const data = await availRes.json()
        setAvailability(data)
        // Auto-select model based on what's installed
        if (data.models?.length > 0) {
          const installed = data.models[0]
          if (installed.includes('27b')) setSelectedModel('27b')
          else if (installed.includes('12b')) setSelectedModel('12b')
          else setSelectedModel('4b')
        }
      }

      if (langRes.ok) {
        const data = await langRes.json()
        setLanguages(data.languages || [])
      }
    } catch (err) {
      console.error('Failed to fetch translation settings:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)

    try {
      const response = await fetch('/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: 'Hello, how are you?',
          source_lang: 'en',
          target_lang: defaultTargetLang || 'es',
          model: selectedModel,
        }),
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        throw new Error(error.detail || 'Translation test failed')
      }

      const data = await response.json()
      setTestResult({
        success: true,
        translated: data.translated_text,
      })
    } catch (err) {
      setTestResult({
        success: false,
        error: err instanceof Error ? err.message : 'Test failed',
      })
    } finally {
      setTesting(false)
    }
  }

  if (loading) {
    return (
      <div className="bg-card rounded-xl shadow-lg p-6">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    )
  }

  const isInstalled = availability?.available || false
  const installedModels = availability?.models || []

  return (
    <div className="bg-card rounded-xl shadow-lg p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-2">Translation Settings</h2>
        <p className="text-sm text-muted-foreground">
          Configure TranslateGemma for transcript translation (55 languages)
        </p>
      </div>

      {/* Status */}
      <div className={`p-4 rounded-lg ${isInstalled ? 'bg-green-500/10 border border-green-500/20' : 'bg-yellow-500/10 border border-yellow-500/20'}`}>
        <div className="flex items-start gap-3">
          {isInstalled ? (
            <Check className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
          ) : (
            <AlertCircle className="h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" />
          )}
          <div className="flex-1">
            <div className="font-medium text-foreground">
              {isInstalled ? 'TranslateGemma Installed' : 'TranslateGemma Not Installed'}
            </div>
            {isInstalled ? (
              <div className="text-sm text-muted-foreground mt-1">
                Models: {installedModels.join(', ')}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground mt-1">
                Install with: <code className="bg-muted px-1.5 py-0.5 rounded">ollama pull translategemma</code>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Model Size Selection */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Model Size
        </label>
        <div className="grid grid-cols-3 gap-2">
          {MODEL_SIZES.map((model) => {
            const isModelInstalled = installedModels.some(m => m.includes(model.value))
            return (
              <button
                key={model.value}
                type="button"
                onClick={() => setSelectedModel(model.value)}
                disabled={!isInstalled}
                className={`p-3 rounded-lg border-2 text-left transition-all ${
                  selectedModel === model.value
                    ? 'border-primary bg-primary/10'
                    : 'border-border bg-background hover:border-primary/50'
                } ${!isInstalled ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-foreground text-sm">{model.label}</span>
                  {isModelInstalled && (
                    <Check className="h-3 w-3 text-green-500" />
                  )}
                </div>
                <div className="text-xs text-muted-foreground">{model.desc}</div>
              </button>
            )
          })}
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          Larger models provide better translation quality but require more memory
        </p>
      </div>

      {/* Default Target Language */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Default Target Language
        </label>
        <select
          value={defaultTargetLang}
          onChange={(e) => setDefaultTargetLang(e.target.value)}
          disabled={!isInstalled}
          className="w-full h-10 px-3 rounded-lg border border-input bg-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
        >
          <option value="">No default (ask each time)</option>
          {languages.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.name}
            </option>
          ))}
        </select>
      </div>

      {/* Test Result */}
      {testResult && (
        <div
          className={`p-4 rounded-lg ${
            testResult.success
              ? 'bg-green-500/10 border border-green-500/20'
              : 'bg-destructive/10 border border-destructive/20'
          }`}
        >
          <div className="flex items-start gap-3">
            {testResult.success ? (
              <Check className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1 min-w-0">
              <div className="font-medium text-foreground">
                {testResult.success ? 'Translation successful!' : 'Translation failed'}
              </div>
              {testResult.translated && (
                <div className="text-sm text-muted-foreground mt-1">
                  "Hello, how are you?" → "{testResult.translated}"
                </div>
              )}
              {testResult.error && (
                <div className="text-sm text-destructive mt-1">{testResult.error}</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Test Button */}
      <Button
        onClick={handleTest}
        disabled={testing || !isInstalled}
        variant="outline"
        className="w-full"
      >
        {testing ? (
          <>
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            Testing...
          </>
        ) : (
          <>
            <Zap className="h-4 w-4 mr-2" />
            Test Translation
          </>
        )}
      </Button>
    </div>
  )
}
