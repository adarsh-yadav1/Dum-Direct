import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { ErrorNote } from '../components/ui'
import { button, field } from '../components/styles'
import { safeNext } from '../lib/nav'
import { useAuth } from '../state/AuthContext'

export function SignIn() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))

  const [mode, setMode] = useState<'signin' | 'register'>('signin')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [marketing, setMarketing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'signin') await login(email, password)
      else await register({ name, email, password, phone, marketing_opt_in: marketing })
      void navigate(next, { replace: true })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const creating = mode === 'register'
  return (
    <main className="mx-auto max-w-md space-y-5 px-4 py-8">
      <h1 className="text-3xl font-bold">{creating ? 'Create your account' : 'Sign in to order'}</h1>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        {creating && (
          <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Name</span>
            <input required value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={120} className={field} /></label>
        )}
        <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Email</span>
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" className={field} /></label>
        {creating && (
          <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Mobile number (optional)</span>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="numeric" autoComplete="tel-national" placeholder="10-digit number" className={field} /></label>
        )}
        <label className="block"><span className="mb-1.5 block text-sm font-medium text-muted">Password{creating && ' (at least 8 characters)'}</span>
          <input required type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={creating ? 'new-password' : 'current-password'} minLength={creating ? 8 : undefined} maxLength={128} className={field} /></label>
        {creating && (
          <label className="flex items-start gap-3 text-sm">
            <input type="checkbox" checked={marketing} onChange={(e) => setMarketing(e.target.checked)} className="mt-0.5 size-4 accent-indigo" />
            <span>Send me offers by SMS or WhatsApp. Leave this off and we only message you about your orders.</span>
          </label>
        )}
        {error && <ErrorNote>{error}</ErrorNote>}
        <button type="submit" disabled={busy} className={button.primary + ' w-full'}>{busy ? 'Please wait…' : creating ? 'Create account' : 'Sign in'}</button>
      </form>
      <p className="text-sm text-muted">
        {creating ? 'Already have an account? ' : 'New here? '}
        <button type="button" onClick={() => { setMode(creating ? 'signin' : 'register'); setError(null) }} className="font-semibold text-indigo underline">
          {creating ? 'Sign in' : 'Create an account'}
        </button>
      </p>
      <p className="text-sm"><Link to="/" className="text-indigo underline">Back to the menu</Link></p>
    </main>
  )
}
