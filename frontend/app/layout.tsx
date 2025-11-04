import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import './globals.css';
import { HealthBanner } from './components/HealthBanner';

export const metadata: Metadata = {
  title: 'Propertyfish',
  description: 'Propertyfish frontend shell',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <HealthBanner />
        <div className="container">{children}</div>
      </body>
    </html>
  );
}
