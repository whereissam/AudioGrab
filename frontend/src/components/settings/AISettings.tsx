import { useState, useEffect } from 'react'
import { Loader2, Check, AlertCircle, Zap, Eye, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type AIProvider = 'ollama' | 'openai' | 'anthropic' | 'groq' | 'deepseek' | 'gemini' | 'custom'

interface AIProviderInfo {
  name: string
  display_name: string
  models: string[]
  requires_api_key: boolean
  default_base_url: string | null
}

interface AISettings {
  provider: AIProvider
  model: string
  base_url: string | null
  has_api_key: boolean
}

const PROVIDER_INFO: Record<AIProvider, AIProviderInfo> = {
  ollama: {
    name: 'ollama',
    display_name: 'Ollama',
    models: ['llama3.2', 'llama3.1', 'mistral', 'gemma2', 'phi3', 'qwen2.5'],
    requires_api_key: false,
    default_base_url: 'http://localhost:11434',
  },
  openai: {
    name: 'openai',
    display_name: 'OpenAI',
    models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'],
    requires_api_key: true,
    default_base_url: null,
  },
  anthropic: {
    name: 'anthropic',
    display_name: 'Anthropic',
    models: [
      'claude-3-haiku-20240307',
      'claude-3-sonnet-20240229',
      'claude-3-opus-20240229',
      'claude-3-5-sonnet-20241022',
    ],
    requires_api_key: true,
    default_base_url: null,
  },
  groq: {
    name: 'groq',
    display_name: 'Groq',
    models: [
      'llama-3.1-70b-versatile',
      'llama-3.1-8b-instant',
      'mixtral-8x7b-32768',
      'gemma2-9b-it',
    ],
    requires_api_key: true,
    default_base_url: null,
  },
  deepseek: {
    name: 'deepseek',
    display_name: 'DeepSeek',
    models: ['deepseek-chat', 'deepseek-coder'],
    requires_api_key: true,
    default_base_url: null,
  },
  gemini: {
    name: 'gemini',
    display_name: 'Google Gemini',
    models: ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-exp'],
    requires_api_key: true,
    default_base_url: null,
  },
  custom: {
    name: 'custom',
    display_name: 'Custom (OpenAI-compatible)',
    models: [],
    requires_api_key: false,
    default_base_url: null,
  },
}

const PROVIDERS: AIProvider[] = ['ollama', 'openai', 'anthropic', 'groq', 'deepseek', 'gemini', 'custom']

export function AISettings() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{
    success: boolean
    error?: string
    response_time_ms?: number
    response_preview?: string
  } | null>(null)

  const [provider, setProvider] = useState<AIProvider>('ollama')
  const [model, setModel] = useState('llama3.2')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [hasExistingKey, setHasExistingKey] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)

  // Fetch current settings on mount
  useEffect(() => {
    fetchSettings()
  }, [])

  // Update model and base URL when provider changes
  useEffect(() => {
    const info = PROVIDER_INFO[provider]
    if (info.models.length > 0 && !info.models.includes(model)) {
      setModel(info.models[0])
    }
    if (info.default_base_url && !baseUrl) {
      setBaseUrl(info.default_base_url)
    }
    // Clear test result when provider changes
    setTestResult(null)
  }, [provider])

  const fetchSettings = async () => {
    try {
      const response = await fetch('/api/ai/settings')
      if (response.ok) {
        const data: AISettings = await response.json()
        setProvider(data.provider)
        setModel(data.model)
        setBaseUrl(data.base_url || '')
        setHasExistingKey(data.has_api_key)
      }
    } catch (err) {
      console.error('Failed to fetch AI settings:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setSuccess(null)

    try {
      const info = PROVIDER_INFO[provider]

      // Validate required fields
      if (info.requires_api_key && !apiKey && !hasExistingKey) {
        throw new Error(`${info.display_name} requires an API key`)
      }

      const body: Record<string, unknown> = {
        provider,
        model,
      }

      // Only send API key if user entered a new one
      if (apiKey) {
        body.api_key = apiKey
      }

      // Send base URL for Ollama and custom providers
      if (provider === 'ollama' || provider === 'custom') {
        body.base_url = baseUrl || info.default_base_url
      }

      const response = await fetch('/api/ai/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to save settings')
      }

      const data = await response.json()
      setHasExistingKey(data.has_api_key)
      setApiKey('') // Clear the input after successful save
      setSuccess('Settings saved successfully')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    setError(null)

    try {
      const info = PROVIDER_INFO[provider]

      const body: Record<string, unknown> = {
        provider,
        model,
      }

      // Use entered API key or existing one
      if (apiKey) {
        body.api_key = apiKey
      }

      if (provider === 'ollama' || provider === 'custom') {
        body.base_url = baseUrl || info.default_base_url
      }

      const response = await fetch('/api/ai/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      const data = await response.json()
      setTestResult(data)
    } catch (err) {
      setTestResult({
        success: false,
        error: err instanceof Error ? err.message : 'Connection test failed',
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

  const currentProviderInfo = PROVIDER_INFO[provider]

  return (
    <div className="bg-card rounded-xl shadow-lg p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-2">AI Provider</h2>
        <p className="text-sm text-muted-foreground">
          Configure the AI provider used for transcript summarization
        </p>
      </div>

      {/* Provider Selection */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Provider
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {PROVIDERS.map((p) => {
            const info = PROVIDER_INFO[p]
            return (
              <button
                key={p}
                type="button"
                onClick={() => setProvider(p)}
                className={`p-3 rounded-lg border-2 text-left transition-all ${
                  provider === p
                    ? 'border-primary bg-primary/10'
                    : 'border-border bg-background hover:border-primary/50'
                }`}
              >
                <div className="font-medium text-foreground text-sm">{info.display_name}</div>
                <div className="text-xs text-muted-foreground">
                  {info.requires_api_key ? 'API key required' : 'Local / Free'}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Model Selection */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-2">
          Model
        </label>
        {currentProviderInfo.models.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {currentProviderInfo.models.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setModel(m)}
                className={`px-3 py-1.5 rounded-lg border text-sm transition-all ${
                  model === m
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-background text-foreground hover:border-primary/50'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        ) : (
          <Input
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="Enter model name"
            className="h-10"
          />
        )}
      </div>

      {/* API Key */}
      {currentProviderInfo.requires_api_key && (
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            API Key
            {hasExistingKey && (
              <span className="ml-2 text-xs text-green-600 font-normal">
                (configured)
              </span>
            )}
          </label>
          <div className="relative">
            <Input
              type={showApiKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={hasExistingKey ? 'Enter new key to update' : 'Enter API key'}
              className="h-10 pr-10"
            />
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              {showApiKey ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </button>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Your API key is stored securely and never exposed
          </p>
        </div>
      )}

      {/* Base URL */}
      {(provider === 'ollama' || provider === 'custom') && (
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Base URL
          </label>
          <Input
            type="url"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={currentProviderInfo.default_base_url || 'https://api.example.com/v1'}
            className="h-10"
          />
          <p className="text-xs text-muted-foreground mt-1">
            {provider === 'ollama'
              ? 'URL where Ollama is running (default: http://localhost:11434)'
              : 'OpenAI-compatible API endpoint'}
          </p>
        </div>
      )}

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
                {testResult.success ? 'Connection successful!' : 'Connection failed'}
              </div>
              {testResult.response_time_ms && (
                <div className="text-sm text-muted-foreground">
                  Response time: {testResult.response_time_ms.toFixed(0)}ms
                </div>
              )}
              {testResult.error && (
                <div className="text-sm text-destructive mt-1">{testResult.error}</div>
              )}
              {testResult.response_preview && (
                <div className="text-sm text-muted-foreground mt-1 truncate">
                  Response: "{testResult.response_preview}"
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Error/Success Messages */}
      {error && (
        <div className="bg-destructive/10 text-destructive p-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-500/10 text-green-600 p-3 rounded-lg text-sm flex items-center gap-2">
          <Check className="h-4 w-4" />
          {success}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-2 text-muted-foreground">
        <Button
          type="button"
          variant="outline"
          onClick={handleTest}
          disabled={testing || saving}
          className="flex-1"
        >
          {testing ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Testing...
            </>
          ) : (
            <>
              <Zap className="h-4 w-4 mr-2" />
              Test Connection
            </>
          )}
        </Button>
        <Button
          type="button"
          onClick={handleSave}
          disabled={saving || testing}
          className="flex-1"
        >
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Check className="h-4 w-4 mr-2" />
              Save Settings
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
