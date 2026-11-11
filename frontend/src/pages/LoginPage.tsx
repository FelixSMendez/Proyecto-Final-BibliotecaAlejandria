import { zodResolver } from '@hookform/resolvers/zod'
import { Eye, EyeOff } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { useAuth } from '../auth/AuthProvider'
import { LogoMark } from '../components/LogoMark'
import { ApiError } from '../lib/api'

const loginSchema = z.object({
  email: z.email('Ingresa un correo válido'),
  password: z.string().min(8, 'La contraseña debe tener al menos 8 caracteres'),
})

type LoginValues = z.infer<typeof loginSchema>

export function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [serverError, setServerError] = useState('')
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: 'lector@alejandria.local', password: 'Cambiar123!' },
  })

  if (user) return <Navigate to="/catalog" replace />

  const submit = async (values: LoginValues) => {
    setServerError('')
    try {
      await login(values.email, values.password)
      navigate('/catalog')
    } catch (error) {
      setServerError(error instanceof ApiError ? error.message : 'No fue posible iniciar sesión')
    }
  }

  return (
    <div className="login-page">
      <div className="login-image" role="img" aria-label="Sala histórica de lectura" />
      <section className="login-panel">
        <div className="login-form-wrap">
          <LogoMark compact />
          <h1>Bienvenido a Alejandría</h1>
          <p className="login-copy">Ingresa para explorar el catálogo y consultar al bibliotecario virtual.</p>
          <form onSubmit={handleSubmit(submit)} className="auth-form">
            <label>
              <span>Correo electrónico</span>
              <input type="email" autoComplete="email" {...register('email')} />
              {errors.email && <small className="field-error">{errors.email.message}</small>}
            </label>
            <label>
              <span>Contraseña</span>
              <div className="password-control">
                <input type={showPassword ? 'text' : 'password'} autoComplete="current-password" {...register('password')} />
                <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}>
                  {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>
              {errors.password && <small className="field-error">{errors.password.message}</small>}
            </label>
            {serverError && <p className="form-error" role="alert">{serverError}</p>}
            <button className="primary-button primary-button--wide" disabled={isSubmitting}>
              {isSubmitting ? 'Abriendo la biblioteca…' : 'Iniciar sesión'}
            </button>
          </form>
          <p className="login-note">Acceso reservado para lectores registrados</p>
        </div>
      </section>
    </div>
  )
}
