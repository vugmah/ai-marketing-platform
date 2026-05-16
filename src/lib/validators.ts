/**
 * validators - Client-side form validation utilities
 * Real-time validation feedback with descriptive error messages.
 */

// ─── Types ───────────────────────────────────────────────

export interface ValidationRule<T = string> {
  validator: (value: T) => boolean;
  message: string;
}

export interface FieldValidation<T = string> {
  rules: ValidationRule<T>[];
  required?: boolean;
  requiredMessage?: string;
}

export type ValidationResult =
  | { isValid: true; error: null }
  | { isValid: false; error: string };

// ─── Built-in Validators ─────────────────────────────────

export const validators = {
  /** Required field check */
  required(message = "Bu alan zorunludur"): ValidationRule {
    return {
      validator: (v: unknown) => {
        if (typeof v === "string") return v.trim().length > 0;
        if (typeof v === "number") return !isNaN(v);
        if (Array.isArray(v)) return v.length > 0;
        return v !== null && v !== undefined;
      },
      message,
    };
  },

  /** Minimum length */
  minLength(min: number, message?: string): ValidationRule<string> {
    return {
      validator: (v) => v.length >= min,
      message: message || `En az ${min} karakter olmalıdır`,
    };
  },

  /** Maximum length */
  maxLength(max: number, message?: string): ValidationRule<string> {
    return {
      validator: (v) => v.length <= max,
      message: message || `En fazla ${max} karakter olabilir`,
    };
  },

  /** Email format */
  email(message = "Geçerli bir e-posta adresi giriniz"): ValidationRule<string> {
    return {
      validator: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v),
      message,
    };
  },

  /** Phone number (Azerbaijan & international) */
  phone(message = "Geçerli bir telefon numarası giriniz"): ValidationRule<string> {
    return {
      validator: (v) =>
        /^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$/im.test(v),
      message,
    };
  },

  /** URL format */
  url(message = "Geçerli bir URL giriniz"): ValidationRule<string> {
    return {
      validator: (v) => {
        try {
          new URL(v);
          return true;
        } catch {
          return false;
        }
      },
      message,
    };
  },

  /** Strong password */
  strongPassword(
    message = "Şifre en az 8 karakter, 1 büyük harf, 1 küçük harf, 1 rakam ve 1 özel karakter içermelidir"
  ): ValidationRule<string> {
    return {
      validator: (v) =>
        /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_#^])[A-Za-z\d@$!%*?&_#^]{8,}$/.test(
          v
        ),
      message,
    };
  },

  /** Password match */
  match(
    compareValue: string,
    message = "Şifreler eşleşmiyor"
  ): ValidationRule<string> {
    return {
      validator: (v) => v === compareValue,
      message,
    };
  },

  /** Minimum numeric value */
  min(min: number, message?: string): ValidationRule<string> {
    return {
      validator: (v) => {
        const n = parseFloat(v);
        return !isNaN(n) && n >= min;
      },
      message: message || `Minimum değer: ${min}`,
    };
  },

  /** Maximum numeric value */
  max(max: number, message?: string): ValidationRule<string> {
    return {
      validator: (v) => {
        const n = parseFloat(v);
        return !isNaN(n) && n <= max;
      },
      message: message || `Maksimum değer: ${max}`,
    };
  },

  /** Positive number */
  positive(message = "Pozitif bir değer giriniz"): ValidationRule<string> {
    return {
      validator: (v) => {
        const n = parseFloat(v);
        return !isNaN(n) && n > 0;
      },
      message,
    };
  },

  /** Alphanumeric */
  alphanumeric(message = "Sadece harf ve rakam kullanabilirsiniz"): ValidationRule<string> {
    return {
      validator: (v) => /^[a-zA-Z0-9\s]+$/.test(v),
      message,
    };
  },

  /** No special characters */
  noSpecialChars(message = "Özel karakterler kullanılamaz"): ValidationRule<string> {
    return {
      validator: (v) => !/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]+/.test(v),
      message,
    };
  },

  /** Custom regex */
  regex(pattern: RegExp, message: string): ValidationRule<string> {
    return {
      validator: (v) => pattern.test(v),
      message,
    };
  },
};

// ─── Password Strength ───────────────────────────────────

export type PasswordStrength = "weak" | "fair" | "good" | "strong";

export function getPasswordStrength(password: string): {
  strength: PasswordStrength;
  score: number;
  feedback: string;
  color: string;
  requirements: Array<{ label: string; met: boolean }>;
} {
  const checks = {
    length: password.length >= 8,
    lowercase: /[a-z]/.test(password),
    uppercase: /[A-Z]/.test(password),
    number: /\d/.test(password),
    special: /[@$!%*?&_#^]/.test(password),
  };

  const score = Object.values(checks).filter(Boolean).length;

  let strength: PasswordStrength;
  let feedback: string;
  let color: string;

  if (score <= 1) {
    strength = "weak";
    feedback = "Çok zayıf - Daha güçlü bir şifre girin";
    color = "#DC2626";
  } else if (score <= 2) {
    strength = "fair";
    feedback = "Zayıf - Ekstra güvenlik önlemleri ekleyin";
    color = "#D97706";
  } else if (score <= 3) {
    strength = "good";
    feedback = "İyi - Birkaç iyileştirme daha yapabilirsiniz";
    color = "#2563EB";
  } else {
    strength = "strong";
    feedback = "Güçlü - Mükemmel şifre güvenliği";
    color = "#059669";
  }

  const requirements = [
    { label: "En az 8 karakter", met: checks.length },
    { label: "Bir küçük harf (a-z)", met: checks.lowercase },
    { label: "Bir büyük harf (A-Z)", met: checks.uppercase },
    { label: "Bir rakam (0-9)", met: checks.number },
    { label: "Bir özel karakter", met: checks.special },
  ];

  return { strength, score, feedback, color, requirements };
}

// ─── Validate Single Field ───────────────────────────────

export function validateField(
  value: string,
  field: FieldValidation<string>
): ValidationResult {
  if (field.required && value.trim().length === 0) {
    return {
      isValid: false,
      error: field.requiredMessage || "Bu alan zorunludur",
    };
  }

  if (!field.required && value.trim().length === 0) {
    return { isValid: true, error: null };
  }

  for (const rule of field.rules) {
    if (!rule.validator(value)) {
      return { isValid: false, error: rule.message };
    }
  }

  return { isValid: true, error: null };
}

// ─── Validate Form ──────────────────────────────────────

export function validateForm<T extends Record<string, string>>(
  values: T,
  schema: Record<keyof T, FieldValidation<string>>
): {
  isValid: boolean;
  errors: Partial<Record<keyof T, string>>;
  firstError: { field: keyof T; message: string } | null;
} {
  const errors: Partial<Record<keyof T, string>> = {};
  let firstError: { field: keyof T; message: string } | null = null;

  for (const key of Object.keys(schema) as (keyof T)[]) {
    const result = validateField(values[key], schema[key]);
    if (!result.isValid) {
      errors[key] = result.error;
      if (!firstError) {
        firstError = { field: key, message: result.error };
      }
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
    firstError,
  };
}

// ─── Common Validation Schemas ──────────────────────────

export const validationSchemas = {
  /** User login form */
  login: {
    email: {
      required: true,
      rules: [validators.email()],
    } as FieldValidation<string>,
    password: {
      required: true,
      rules: [validators.minLength(6)],
    } as FieldValidation<string>,
  },

  /** User registration form */
  register: {
    full_name: {
      required: true,
      rules: [
        validators.minLength(2, "İsim en az 2 karakter olmalıdır"),
        validators.maxLength(100),
        validators.noSpecialChars(),
      ],
    } as FieldValidation<string>,
    email: {
      required: true,
      rules: [validators.email()],
    } as FieldValidation<string>,
    password: {
      required: true,
      rules: [validators.strongPassword()],
    } as FieldValidation<string>,
    confirm_password: {
      required: true,
      rules: [validators.required("Şifre onayı gereklidir")],
    } as FieldValidation<string>,
  },

  /** Branch form */
  branch: {
    name: {
      required: true,
      rules: [
        validators.minLength(2),
        validators.maxLength(100),
      ],
    } as FieldValidation<string>,
    city: {
      required: true,
      rules: [validators.minLength(2)],
    } as FieldValidation<string>,
    address: {
      required: true,
      rules: [validators.minLength(5)],
    } as FieldValidation<string>,
    phone: {
      required: true,
      rules: [validators.phone()],
    } as FieldValidation<string>,
  },

  /** Company form */
  company: {
    name: {
      required: true,
      rules: [validators.minLength(2), validators.maxLength(200)],
    } as FieldValidation<string>,
    industry: {
      required: true,
      rules: [validators.minLength(2)],
    } as FieldValidation<string>,
    contact_email: {
      required: true,
      rules: [validators.email()],
    } as FieldValidation<string>,
  },

  /** Campaign form */
  campaign: {
    name: {
      required: true,
      rules: [validators.minLength(3), validators.maxLength(200)],
    } as FieldValidation<string>,
    budget: {
      required: true,
      rules: [validators.positive()],
    } as FieldValidation<string>,
    platform: {
      required: true,
      rules: [validators.minLength(2)],
    } as FieldValidation<string>,
  },
};

// ─── Real-time Validation Hook ───────────────────────────

import { useState, useCallback } from "react";

export function useFieldValidation(initialValue = "", field: FieldValidation<string>) {
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  const validate = useCallback(
    (v: string = value) => {
      const result = validateField(v, field);
      setError(result.isValid ? null : result.error);
      return result.isValid;
    },
    [value, field]
  );

  const handleChange = useCallback(
    (newValue: string) => {
      setValue(newValue);
      if (touched) {
        validate(newValue);
      }
    },
    [touched, validate]
  );

  const handleBlur = useCallback(() => {
    setTouched(true);
    validate(value);
  }, [value, validate]);

  const handleFocus = useCallback(() => {
    setError(null);
  }, []);

  return {
    value,
    error,
    touched,
    setValue,
    handleChange,
    handleBlur,
    handleFocus,
    validate,
  };
}
