import { forwardRef } from 'react';
import { cn } from '@/shared/utils/cn';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'destructive' | 'outline';
  size?: 'sm' | 'md' | 'lg';
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'inline-flex items-center justify-center gap-2 rounded-md font-semibold transition-colors duration-150',
          'focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/15',
          'disabled:pointer-events-none disabled:opacity-50',
          {
            'bg-primary text-primary-foreground hover:bg-primary-hover': variant === 'primary',
            'border border-line bg-card text-foreground hover:bg-muted': variant === 'secondary',
            'text-foreground hover:bg-muted': variant === 'ghost',
            'bg-destructive text-destructive-foreground hover:bg-[#A34747]': variant === 'destructive',
            'border border-line bg-card text-primary hover:bg-primary-soft': variant === 'outline',
          },
          {
            'h-[30px] px-3 text-xs': size === 'sm',
            'h-[38px] px-4 text-[13px]': size === 'md',
            'h-11 px-5 text-sm': size === 'lg',
          },
          className,
        )}
        {...props}
      />
    );
  },
);

Button.displayName = 'Button';
