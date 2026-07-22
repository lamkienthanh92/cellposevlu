import { useRef, useState } from "react";

export default function UploadPanel({ onSelect, files, disabled }) {
  const inputRef = useRef(null);
  const folderInputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (fileList) => {
    const images = Array.from(fileList).filter((f) => f.type.startsWith("image/"));
    if (images.length) onSelect(images);
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
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        hidden
        disabled={disabled}
        onChange={(e) => handleFiles(e.target.files)}
      />
      {/* webkitdirectory lets the user pick an entire folder (Chrome/Edge/Safari) */}
      <input
        ref={folderInputRef}
        type="file"
        webkitdirectory="true"
        directory="true"
        multiple
        hidden
        disabled={disabled}
        onChange={(e) => handleFiles(e.target.files)}
      />

      {files.length > 0 ? (
        <div className="dropzone__filelist">
          <span className="dropzone__filelist-count">{files.length} image(s) selected</span>
          <span className="dropzone__filelist-names">
            {files.slice(0, 4).map((f) => f.name).join(", ")}
            {files.length > 4 ? `, +${files.length - 4} more` : ""}
          </span>
        </div>
      ) : (
        <div className="dropzone__empty">
          <span className="dropzone__label">Drop Gram-stain images here</span>
          <span className="dropzone__hint">or use the buttons below</span>
        </div>
      )}

      <div className="dropzone__actions">
        <button type="button" disabled={disabled} onClick={() => inputRef.current?.click()}>
          Choose image(s)
        </button>
        <button type="button" disabled={disabled} onClick={() => folderInputRef.current?.click()}>
          Choose whole folder
        </button>
      </div>
    </div>
  );
}
