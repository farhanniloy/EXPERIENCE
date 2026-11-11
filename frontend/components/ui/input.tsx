import { InputHTMLAttributes, forwardRef } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement>;

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className = "", ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={`h-12 w-full rounded-full border border-[#E8E4DC] bg-white px-4 text-sm text-[#20201F] placeholder:text-[#77736D] outline-none transition focus:border-[#75404A] focus:ring-2 focus:ring-[#75404A]/10 ${className}`}
      {...props}
    />
  );
});
