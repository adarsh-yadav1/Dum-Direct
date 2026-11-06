import { BrowserRouter, Route, Routes } from 'react-router'

import { Layout } from './components/Layout'
import { Cart } from './pages/Cart'
import { Checkout } from './pages/Checkout'
import { Kitchen } from './pages/Kitchen'
import { OrderPage } from './pages/OrderPage'
import { SignIn } from './pages/SignIn'
import { Storefront } from './pages/Storefront'
import { AuthProvider } from './state/AuthContext'
import { CartProvider } from './state/CartContext'
import { LocationProvider } from './state/LocationContext'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <LocationProvider>
          <CartProvider>
            <Routes>
              <Route path="kitchen" element={<Kitchen />} />
              <Route element={<Layout />}>
                <Route index element={<Storefront />} />
                <Route path="cart" element={<Cart />} />
                <Route path="checkout" element={<Checkout />} />
                <Route path="orders/:code" element={<OrderPage />} />
                <Route path="signin" element={<SignIn />} />
                <Route path="*" element={<Storefront />} />
              </Route>
            </Routes>
          </CartProvider>
        </LocationProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
