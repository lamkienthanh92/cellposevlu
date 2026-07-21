import { useRef, useState } from "react";

export default function UploadPanel({ onSelect, previewUrl, disabled }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (files) => {
    const file = files?.[0];
    if (file) onSelect(file);
  };

  return (
    <div
      className={`dropzone ${dragging ? "dropzone--active" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
      onClick={() => !disabled && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        hidden
        disabled={disabled}
        onChange={(e) => handleFiles(e.target.files)}
      />

      {previewUrl ? (
        <img src={previewUrl} alt="Selected smear" className="dropzone__preview" />
      ) : (
        <div className="dropzone__empty">
          <span className="dropzone__label">Drop a Gram-stain image here</span>
          <span className="dropzone__hint">or click to browse — JPG, PNG, TIFF</span>
        </div>
      )}
    </div>
  );
}
