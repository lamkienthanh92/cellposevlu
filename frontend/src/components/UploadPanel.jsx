import { useRef, useState } from "react";

const IMAGE_EXT = /\.(jpe?g|png|tiff?|bmp)$/i;

export default function UploadPanel({
  mode,
  onModeChange,
  onSelectSingle,
  onSelectBatch,
  previewUrl,
  fileCount,
  disabled,
}) {
  const singleInputRef = useRef(null);
  const folderInputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleSingleFiles = (files) => {
    const file = files?.[0];
    if (file) onSelectSingle(file);
  };

  const handleFolderFiles = (fileList) => {
    const images = Array.from(fileList).filter((f) => IMAGE_EXT.test(f.name));
    if (images.length) onSelectBatch(images);
  };

  return (
    <div className="upload-panel">
      <div className="mode-toggle">
        <button
          type="button"
          className={`mode-toggle__btn ${mode === "single" ? "mode-toggle__btn--active" : ""}`}
          onClick={() => onModeChange("single")}
          disabled={disabled}
        >
          Một ảnh
        </button>
        <button
          type="button"
          className={`mode-toggle__btn ${mode === "batch" ? "mode-toggle__btn--active" : ""}`}
          onClick={() => onModeChange("batch")}
          disabled={disabled}
        >
          Cả thư mục (batch)
        </button>
      </div>

      {mode === "single" ? (
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
            handleSingleFiles(e.dataTransfer.files);
          }}
          onClick={() => !disabled && singleInputRef.current?.click()}
        >
          <input
            ref={singleInputRef}
            type="file"
            accept="image/*"
            hidden
            disabled={disabled}
            onChange={(e) => handleSingleFiles(e.target.files)}
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
      ) : (
        <div
          className="dropzone dropzone--folder"
          onClick={() => !disabled && folderInputRef.current?.click()}
        >
          <input
            ref={folderInputRef}
            type="file"
            webkitdirectory=""
            directory=""
            multiple
            hidden
            disabled={disabled}
            onChange={(e) => handleFolderFiles(e.target.files)}
          />
          <div className="dropzone__empty">
            <span className="dropzone__label">
              {fileCount > 0 ? `${fileCount} ảnh đã chọn` : "Click để chọn một thư mục ảnh"}
            </span>
            <span className="dropzone__hint">
              Toàn bộ JPG/PNG/TIFF trong thư mục sẽ được xử lý (chọn lại để đổi thư mục)
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
