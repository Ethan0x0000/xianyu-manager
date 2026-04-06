export type LoginRequest = {
  username: string
  password: string
}

export type LoginResponse = {
  token: string
}

export type VerifyResponse = {
  username: string
}

export type LogoutResponse = {
  success?: boolean
}

export type ApiError = {
  detail?: string
  message?: string
}
