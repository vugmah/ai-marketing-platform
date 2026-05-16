/**
 * useFileUpload - File upload hook with progress tracking,
 * validation, and drag-and-drop support.
 */
import { useState, useCallback, useRef } from "react";

// ─── Types ───────────────────────────────────────────────

export interface FileUploadOptions {
  accept?: string[];
  maxSize?: number; // in bytes
  maxFiles?: number;
  multiple?: boolean;
  onUpload?: (file: File) => Promise<string>;
  onError?: (error: string) => void;
}

export interface UploadFile {
  id: string;
  file: File;
  name: string;
  size: number;
  type: string;
  progress: number;
  status: "pending" | "uploading" | "success" | "error";
  url?: string;
  error?: string;
}

// ─── Helper Functions ────────────────────────────────────

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function generateId(): string {
  return `file-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function validateFile(
  file: File,
  options: FileUploadOptions
): string | null {
  const { accept, maxSize } = options;

  // Check file type
  if (accept && accept.length > 0) {
    const isAccepted = accept.some((type) => {
      if (type.includes("/*")) {
        return file.type.startsWith(type.replace("/*", ""));
      }
      return file.type === type;
    });
    if (!isAccepted) {
      return `Dosya türü desteklenmiyor. Kabul edilen: ${accept.join(", ")}`;
    }
  }

  // Check file size
  if (maxSize && file.size > maxSize) {
    return `Dosya boyutu ${formatFileSize(maxSize)} değerini aşıyor`;
  }

  return null;
}

// ─── Main Hook ───────────────────────────────────────────

export function useFileUpload(options: FileUploadOptions = {}) {
  const {
    maxFiles = 5,
    multiple = false,
    onUpload,
    onError,
    accept,
    maxSize,
  } = options;

  const [files, setFiles] = useState<UploadFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback(
    (newFiles: FileList | null) => {
      if (!newFiles || newFiles.length === 0) return;

      const filesArray = Array.from(newFiles);

      // Check max files
      if (!multiple && filesArray.length > 1) {
        onError?.("Tek seferde yalnızca 1 dosya yükleyebilirsiniz");
        return;
      }

      const remainingSlots = maxFiles - files.length;
      if (remainingSlots <= 0) {
        onError?.(`En fazla ${maxFiles} dosya yükleyebilirsiniz`);
        return;
      }

      const filesToAdd = filesArray.slice(0, remainingSlots);
      const newUploadFiles: UploadFile[] = [];

      for (const file of filesToAdd) {
        const validationError = validateFile(file, { accept, maxSize });
        if (validationError) {
          onError?.(validationError);
          continue;
        }

        newUploadFiles.push({
          id: generateId(),
          file,
          name: file.name,
          size: file.size,
          type: file.type,
          progress: 0,
          status: "pending",
        });
      }

      setFiles((prev) => [...prev, ...newUploadFiles]);

      // Auto-start upload if handler provided
      if (onUpload) {
        newUploadFiles.forEach((uploadFile) => {
          startUpload(uploadFile.id);
        });
      }
    },
    [files.length, maxFiles, multiple, onUpload, onError, accept, maxSize]
  );

  const startUpload = useCallback(
    async (fileId: string) => {
      const uploadFile = files.find((f) => f.id === fileId);
      if (!uploadFile || !onUpload) return;

      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId ? { ...f, status: "uploading" as const } : f
        )
      );

      // Simulate progress
      const progressInterval = setInterval(() => {
        setFiles((prev) =>
          prev.map((f) => {
            if (f.id !== fileId || f.status !== "uploading") return f;
            const newProgress = Math.min(f.progress + Math.random() * 25, 90);
            return { ...f, progress: newProgress };
          })
        );
      }, 300);

      try {
        const url = await onUpload(uploadFile.file);
        clearInterval(progressInterval);
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId
              ? { ...f, status: "success" as const, progress: 100, url }
              : f
          )
        );
      } catch {
        clearInterval(progressInterval);
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId
              ? {
                  ...f,
                  status: "error" as const,
                  error: "Yükleme başarısız oldu",
                }
              : f
          )
        );
        onError?.(`"${uploadFile.name}" yüklenirken hata oluştu`);
      }
    },
    [files, onUpload, onError]
  );

  const removeFile = useCallback((fileId: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== fileId));
  }, []);

  const clearFiles = useCallback(() => {
    setFiles([]);
  }, []);

  // Drag and drop handlers
  const handleDragEnter = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(true);
    },
    []
  );

  const handleDragLeave = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
    },
    []
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
    },
    []
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      addFiles(e.target.files);
      // Reset input so same file can be selected again
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    },
    [addFiles]
  );

  const openFileDialog = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const getRootProps = useCallback(
    () => ({
      onDragEnter: handleDragEnter,
      onDragLeave: handleDragLeave,
      onDragOver: handleDragOver,
      onDrop: handleDrop,
      onClick: openFileDialog,
      role: "button",
      tabIndex: 0,
      "aria-label": "Dosya yüklemek için tıklayın veya sürükleyin",
    }),
    [
      handleDragEnter,
      handleDragLeave,
      handleDragOver,
      handleDrop,
      openFileDialog,
    ]
  );

  const getInputProps = useCallback(
    () => ({
      ref: inputRef,
      type: "file" as const,
      onChange: handleInputChange,
      accept: accept?.join(","),
      multiple,
      style: { display: "none" as const },
    }),
    [handleInputChange, accept, multiple]
  );

  return {
    // State
    files,
    isDragging,
    totalFiles: files.length,
    uploadingCount: files.filter((f) => f.status === "uploading").length,
    completedCount: files.filter((f) => f.status === "success").length,
    errorCount: files.filter((f) => f.status === "error").length,
    hasErrors: files.some((f) => f.status === "error"),
    isComplete: files.length > 0 && files.every((f) => f.status === "success"),
    totalSize: files.reduce((sum, f) => sum + f.size, 0),

    // Actions
    addFiles,
    removeFile,
    clearFiles,
    startUpload,
    openFileDialog,

    // Drag & drop
    getRootProps,
    getInputProps,

    // Helpers
    formatFileSize,
  };
}
