import './globals.css';
import type { ReactNode } from 'react';
import { Inter } from 'next/font/google';

export const metadata = { title: 'PropertyFish' };

const inter = Inter({ subsets: ['latin'] });

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-neutral-950 text-neutral-100`}>
        {children}
      </body>
    </html>
  );
}
