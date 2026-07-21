# ============================================
# OPTIMIZED GRAM STAIN ANALYSIS - PER IMAGE OUTPUT
# Fast + Complete Features + Population-Level Statistics
# Output: 1 row = 1 image (90+ variables)
# Voting classifier: v1=25, v2_GP=1.1, v2_GN=0.9 (non-influential),
#   v3=0.15, v4=0.10, v5=15 (grid-search optimised; corrected 2026-07,
#   see full_grid_search_20260425_104948.xlsx, composite=0.9932)
# ============================================

from cellpose import models
from skimage import measure, exposure, feature
from scipy import ndimage
import numpy as np
import cv2
import pandas as pd
import matplotlib.pyplot as plt
from google.colab import files
from PIL import Image
import time
from datetime import datetime
import os
import zipfile

# ============================================
# CONFIGURATION
# ============================================

PIXEL_SIZE = 0.1          # um/pixel
PIXEL_AREA = PIXEL_SIZE ** 2

# Five-criterion voting classifier parameters (grid-search optimised)
# Reference: Supplementary Methods S1
GRAM_POS_REF_RGB = np.array([100, 100, 180])   # Purple reference prototype
GRAM_NEG_REF_RGB = np.array([200, 130, 140])   # Pink reference prototype
COLOR_DISTANCE_UNCLEAR_MARGIN = 25  # v1: re-optimised 2026-07 (corrected grid-search readout; was mistakenly reported/coded as 15)
BLUE_RED_RATIO_GRAMPOS_MIN = 1.1    # v2_GP: re-optimised (was mistakenly reported/coded as 1.2)
BLUE_RED_RATIO_GRAMNEG_MAX = 0.9    # v2_GN: composite score is flat across the full 0.1-0.9 range (delta ~0.0001); value is effectively arbitrary within that range
BLUE_DARKNESS_THRESHOLD = 0.15      # v3: re-optimised (was mistakenly reported/coded as 0.10)
RED_DARKNESS_THRESHOLD = 0.10       # v4: re-optimised; tied with 0.05 in the grid (was mistakenly reported/coded as 0.30)
CHANNEL_GAP_THRESHOLD = 15          # v5: re-optimised (was mistakenly reported/coded as 5)

# Cell size filters
MIN_CELL_AREA_PX = 20
MAX_CELL_AREA_PX = 2000
TEXTURE_SAMPLE_SIZE = 20

# ============================================
# UPLOAD & EXTRACT IMAGES
# ============================================

uploaded = files.upload()
zip_name = list(uploaded.keys())[0]
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
extract_folder = f'images_{timestamp}'

with zipfile.ZipFile(zip_name, 'r') as zip_ref:
    zip_ref.extractall(extract_folder)

image_files = []
for root, dirs, files_list in os.walk(extract_folder):
    for file in files_list:
        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff')):
            image_files.append(os.path.join(root, file))

# ============================================
# LOAD CELLPOSE MODEL
# ============================================

try:
    model = models.Cellpose(gpu=True, model_type='cyto2')
except AttributeError:
    model = models.CellposeModel(gpu=True, model_type='cyto2')

# ============================================
# HELPER FUNCTIONS
# ============================================

def preprocess_image(img):
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    img_adaptive = exposure.equalize_adapthist(gray, clip_limit=0.03)
    img_adaptive = (img_adaptive * 255).astype(np.uint8)
    img_adaptive_rgb = cv2.cvtColor(img_adaptive, cv2.COLOR_GRAY2RGB)
    return img_adaptive_rgb, gray

def detect_background(img, masks):
    red = img[:,:,0].astype(float)
    green = img[:,:,1].astype(float)
    blue = img[:,:,2].astype(float)
    background_mask = masks == 0
    if np.sum(background_mask) > 100:
        bg_r = np.median(red[background_mask])
        bg_g = np.median(green[background_mask])
        bg_b = np.median(blue[background_mask])
    else:
        bg_r = np.percentile(red, 90)
        bg_g = np.percentile(green, 90)
        bg_b = np.percentile(blue, 90)
    return np.array([bg_r, bg_g, bg_b])

def classify_gram_cell(cell_rgb, background_rgb):
    """
    Five-criterion voting classifier for per-cell Gram classification.
    Parameters optimised by grid search (Supplementary Methods S1):
    v1=25, v2_GP=1.1, v2_GN=0.9 (non-influential), v3=0.15, v4=0.10, v5=15
    (corrected 2026-07 against full_grid_search_20260425_104948.xlsx;
    composite=0.9932, MAE_Gpos=15.6, MAE_Gneg=9.1, r_Gpos=0.9922, r_Gneg=0.9996)
    Returns: ('gram_positive'|'gram_negative'|'unclear', blue_red_ratio)
    """
    cell_r, cell_g, cell_b = cell_rgb
    # Vote 1: Euclidean RGB distance to reference prototypes (weight=2)
    dist_to_grampos = np.linalg.norm(cell_rgb - GRAM_POS_REF_RGB)
    dist_to_gramneg = np.linalg.norm(cell_rgb - GRAM_NEG_REF_RGB)
    # Vote 2: Blue/Red ratio (weight=1)
    blue_red_ratio = cell_b / (cell_r + 1)
    # Votes 3–4: Channel darkness relative to background
    bg_b = background_rgb[2]
    bg_r = background_rgb[0]
    blue_darkness_pct = (bg_b - cell_b) / bg_b if bg_b > 0 else 0
    red_darkness_pct  = (bg_r - cell_r) / bg_r if bg_r > 0 else 0
    votes_pos = 0
    votes_neg = 0
    # Vote 1 (weight=2)
    if dist_to_grampos < dist_to_gramneg - COLOR_DISTANCE_UNCLEAR_MARGIN:
        votes_pos += 2
    elif dist_to_gramneg < dist_to_grampos - COLOR_DISTANCE_UNCLEAR_MARGIN:
        votes_neg += 2
    # Vote 2 (weight=1)
    if blue_red_ratio > BLUE_RED_RATIO_GRAMPOS_MIN:   votes_pos += 1
    elif blue_red_ratio < BLUE_RED_RATIO_GRAMNEG_MAX: votes_neg += 1
    # Vote 3 (weight=1)
    if blue_darkness_pct >= BLUE_DARKNESS_THRESHOLD:  votes_pos += 1
    # Vote 4 (weight=1)
    if red_darkness_pct  >= RED_DARKNESS_THRESHOLD:   votes_neg += 1
    # Vote 5 (weight=1)
    if cell_b < cell_r - CHANNEL_GAP_THRESHOLD:   votes_pos += 1
    elif cell_r < cell_b - CHANNEL_GAP_THRESHOLD: votes_neg += 1
    if votes_pos > votes_neg:   return 'gram_positive',  blue_red_ratio
    elif votes_neg > votes_pos: return 'gram_negative',  blue_red_ratio
    else:                       return 'unclear',         blue_red_ratio

def calculate_snr(cell_intensity, background):
    if len(background) > 0 and background.std() > 0:
        return cell_intensity.mean() / background.std()
    return 0

def calculate_shannon_diversity(values):
    if len(values) == 0: return 0
    hist, _ = np.histogram(values, bins=5)
    hist = hist[hist > 0]
    if len(hist) == 0: return 0
    proportions = hist / hist.sum()
    return -np.sum(proportions * np.log(proportions))

# ============================================
# TEXTURE ANALYSIS (SAMPLED, LOCAL STD)
# ============================================

def analyze_texture_sampled(gray, masks, valid_regions, sample_size=20):
    if len(valid_regions) == 0:
        return {k: 0 for k in ['mean_texture_roughness','std_texture_roughness',
                                'mean_texture_contrast','texture_uniformity',
                                'texture_diversity','texture_range']}
    texture_map = ndimage.generic_filter(gray, np.std, size=5)
    import random
    sampled = random.sample(valid_regions, min(sample_size, len(valid_regions)))
    texture_values, contrast_values = [], []
    for region in sampled:
        cell_mask = masks == region.label
        t = np.mean(texture_map[cell_mask])
        texture_values.append(t)
        contrast_values.append(np.std(gray[cell_mask]))
    if not texture_values:
        return {k: 0 for k in ['mean_texture_roughness','std_texture_roughness',
                                'mean_texture_contrast','texture_uniformity',
                                'texture_diversity','texture_range']}
    return {
        'mean_texture_roughness': np.mean(texture_values),
        'std_texture_roughness':  np.std(texture_values),
        'mean_texture_contrast':  np.mean(contrast_values),
        'texture_uniformity':     100 / (1 + np.std(texture_values)),
        'texture_diversity':      calculate_shannon_diversity(texture_values),
        'texture_range':          np.max(texture_values) - np.min(texture_values)
    }

# ============================================
# EDGE ANALYSIS (CACHED SOBEL GRADIENTS)
# ============================================

def analyze_edges_cached(gray, masks, valid_regions):
    if len(valid_regions) == 0:
        return {k: 0 for k in ['mean_edge_intensity','mean_edge_sharpness',
                                'std_edge_intensity','edge_uniformity','mean_boundary_contrast']}
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    grad = np.sqrt(gx**2 + gy**2)
    edge_int, edge_sharp, bnd_contrast = [], [], []
    for region in valid_regions:
        cell_mask = masks == region.label
        eroded = ndimage.binary_erosion(cell_mask, iterations=1)
        boundary = cell_mask & ~eroded
        if np.sum(boundary) < 5: continue
        edge_int.append(np.mean(grad[boundary]))
        edge_sharp.append(np.percentile(grad[boundary], 75))
        dilated = ndimage.binary_dilation(cell_mask, iterations=2)
        ring = dilated & ~cell_mask
        if np.sum(ring) > 0:
            bnd_contrast.append(abs(np.mean(gray[cell_mask]) - np.mean(gray[ring])))
    if not edge_int:
        return {k: 0 for k in ['mean_edge_intensity','mean_edge_sharpness',
                                'std_edge_intensity','edge_uniformity','mean_boundary_contrast']}
    mean_ei = np.mean(edge_int)
    return {
        'mean_edge_intensity':    mean_ei,
        'mean_edge_sharpness':    np.mean(edge_sharp),
        'std_edge_intensity':     np.std(edge_int),
        'edge_uniformity':        100 - (np.std(edge_int)/mean_ei*100) if mean_ei > 0 else 0,
        'mean_boundary_contrast': np.mean(bnd_contrast) if bnd_contrast else 0
    }

# ============================================
# WALL THICKNESS (DISTANCE TRANSFORM)
# ============================================

def analyze_wall_thickness_fast(masks, valid_regions):
    if len(valid_regions) == 0:
        return {k: 0 for k in ['mean_wall_thickness_estimate','median_wall_thickness_estimate',
                                'std_wall_thickness','cv_wall_thickness','max_wall_thickness']}
    dist_all = ndimage.distance_transform_edt(masks > 0)
    thicknesses = []
    for region in valid_regions:
        d = dist_all[masks == region.label]
        if len(d) > 0:
            thicknesses.append(np.mean(d) * PIXEL_SIZE)
    if not thicknesses:
        return {k: 0 for k in ['mean_wall_thickness_estimate','median_wall_thickness_estimate',
                                'std_wall_thickness','cv_wall_thickness','max_wall_thickness']}
    mt = np.mean(thicknesses)
    return {
        'mean_wall_thickness_estimate':   mt,
        'median_wall_thickness_estimate': np.median(thicknesses),
        'std_wall_thickness':             np.std(thicknesses),
        'cv_wall_thickness':              (np.std(thicknesses)/mt*100) if mt > 0 else 0,
        'max_wall_thickness':             np.max(thicknesses)
    }

# ============================================
# MEMBRANE INTEGRITY
# ============================================

def analyze_membrane_integrity(gray, masks, valid_regions):
    if len(valid_regions) == 0:
        return {k: 0 for k in ['mean_intensity_uniformity','mean_shape_regularity',
                                'membrane_integrity_score','pct_intact_cells','fragmentation_index']}
    uniformities, regularities, intact = [], [], 0
    for region in valid_regions:
        cell_mask = masks == region.label
        cell_pixels = gray[cell_mask]
        if len(cell_pixels) > 10:
            cv = (np.std(cell_pixels)/np.mean(cell_pixels)*100) if np.mean(cell_pixels) > 0 else 100
            u = 100 - min(cv, 100)
            uniformities.append(u)
        else:
            u = 0
        circ = (4*np.pi*region.area)/(region.perimeter**2) if region.perimeter > 0 else 0
        reg = circ * region.solidity
        regularities.append(reg)
        if u > 70 and reg > 0.7: intact += 1
    n = len(valid_regions)
    return {
        'mean_intensity_uniformity':  np.mean(uniformities) if uniformities else 0,
        'mean_shape_regularity':      np.mean(regularities),
        'membrane_integrity_score':   (np.mean(uniformities)+np.mean(regularities)*100)/2 if uniformities else 0,
        'pct_intact_cells':           (intact/n*100) if n > 0 else 0,
        'fragmentation_index':        ((n-intact)/n*100) if n > 0 else 0
    }

# ============================================
# PEPTIDOGLYCAN / CV RETENTION
# ============================================

def analyze_peptidoglycan(img, masks, valid_regions, background_rgb):
    if len(valid_regions) == 0:
        return {k: 0 for k in ['mean_cv_retention','median_cv_retention',
                                'std_cv_retention','cv_retention_range','peptidoglycan_score']}
    blue = img[:,:,2]
    bg_b = background_rgb[2]
    cv_retentions = [bg_b - np.mean(blue[masks == r.label]) for r in valid_regions]
    mean_ret = np.mean(cv_retentions)
    return {
        'mean_cv_retention':    mean_ret,
        'median_cv_retention':  np.median(cv_retentions),
        'std_cv_retention':     np.std(cv_retentions),
        'cv_retention_range':   np.max(cv_retentions) - np.min(cv_retentions),
        'peptidoglycan_score':  np.clip(mean_ret * 3, 0, 100)
    }

# ============================================
# MAIN ANALYSIS FUNCTION
# ============================================

def analyze_image(img_path):
    img_name = os.path.basename(img_path)
    try:
        img_original = cv2.cvtColor(cv2.imread(img_path), cv2.COLOR_BGR2RGB)
        MAX_DIM = 1024
        h, w = img_original.shape[:2]
        if max(h, w) > MAX_DIM:
            scale = MAX_DIM / max(h, w)
            img_original = cv2.resize(img_original, (int(w*scale), int(h*scale)),
                                      interpolation=cv2.INTER_AREA)

        img_prep, gray = preprocess_image(img_original)

        masks, flows, styles = model.eval(
            img_prep, diameter=12, flow_threshold=0.5,
            cellprob_threshold=0.0, channels=[0, 0]
        )

        n_cells = masks.max()
        if n_cells == 0: return None

        background_rgb = detect_background(img_original, masks)
        regions = measure.regionprops(masks, intensity_image=gray)
        valid_regions = [r for r in regions if MIN_CELL_AREA_PX <= r.area <= MAX_CELL_AREA_PX]
        n_valid = len(valid_regions)
        if n_valid == 0: return None

        red   = img_original[:,:,0].astype(float)
        green = img_original[:,:,1].astype(float)
        blue  = img_original[:,:,2].astype(float)
        cell_mask_all   = masks > 0
        background_mask = masks == 0

        # --- SV1: Intensity & Staining ---
        blue_cells = blue[cell_mask_all]
        red_cells  = red[cell_mask_all]
        blue_bg = blue[background_mask]
        red_bg  = red[background_mask]

        sv1_blue_mean    = np.mean(blue_cells)
        sv1_blue_std     = np.std(blue_cells)
        sv1_blue_median  = np.median(blue_cells)
        sv1_blue_cv_pct  = sv1_blue_std / sv1_blue_mean * 100 if sv1_blue_mean > 0 else 0
        sv1_blue_min     = np.min(blue_cells)
        sv1_blue_max     = np.max(blue_cells)
        sv1_red_mean     = np.mean(red_cells)
        sv1_red_std      = np.std(red_cells)
        sv1_red_median   = np.median(red_cells)
        sv1_red_cv_pct   = sv1_red_std / sv1_red_mean * 100 if sv1_red_mean > 0 else 0
        sv1_red_min      = np.min(red_cells)
        sv1_red_max      = np.max(red_cells)

        sv1_blue_bg_mean = np.mean(blue_bg) if len(blue_bg) > 0 else 0
        sv1_blue_bg_std  = np.std(blue_bg)  if len(blue_bg) > 0 else 0
        sv1_red_bg_mean  = np.mean(red_bg)  if len(red_bg)  > 0 else 0
        sv1_red_bg_std   = np.std(red_bg)   if len(red_bg)  > 0 else 0
        sv1_bg_noise     = (sv1_blue_bg_std + sv1_red_bg_std) / 2

        # SV1 Blue/Red ratio = image-level population mean (NOT a per-cell classifier threshold)
        sv1_blue_red_ratio   = sv1_blue_mean / sv1_red_mean if sv1_red_mean > 0 else 0
        sv1_contrast_ratio   = (sv1_blue_mean - sv1_red_mean) / (sv1_blue_mean + sv1_red_mean + 1e-9)
        sv1_color_separation = abs(sv1_blue_mean - sv1_red_mean) / (sv1_blue_mean + sv1_red_mean + 1e-9)
        sv1_staining_quality = sv1_blue_mean / (sv1_blue_std + sv1_red_std + 1e-9)
        sv1_dynamic_range    = (sv1_blue_max - sv1_blue_min + sv1_red_max - sv1_red_min) / 2
        sv1_intensity_balance = min(sv1_blue_mean, sv1_red_mean) / max(sv1_blue_mean, sv1_red_mean + 1e-9)
        sv1_blue_snr     = calculate_snr(blue_cells, blue_bg)
        sv1_red_snr      = calculate_snr(red_cells,  red_bg)
        sv1_combined_snr = (sv1_blue_snr + sv1_red_snr) / 2
        sv1_signal_clarity = (sv1_blue_mean + sv1_red_mean) / (sv1_blue_std + sv1_red_std + 1e-9)
        sv1_noise_ratio    = sv1_bg_noise / ((sv1_blue_mean + sv1_red_mean) / 2 + 1e-9)
        sv1_bg_uniformity  = 100 - sv1_bg_noise

        # --- SV2: Cell Wall (imaging proxies) ---
        tex = analyze_texture_sampled(gray, masks, valid_regions, TEXTURE_SAMPLE_SIZE)
        edg = analyze_edges_cached(gray, masks, valid_regions)
        wth = analyze_wall_thickness_fast(masks, valid_regions)
        mig = analyze_membrane_integrity(gray, masks, valid_regions)
        pep = analyze_peptidoglycan(img_original, masks, valid_regions, background_rgb)

        sv2_wall_quality_score  = (edg['mean_edge_sharpness']/10 + mig['membrane_integrity_score']/2 + pep['peptidoglycan_score']) / 3
        sv2_wall_uniformity     = (edg['edge_uniformity'] + mig['mean_intensity_uniformity']) / 2
        sv2_wall_strength_index = (pep['peptidoglycan_score'] + mig['pct_intact_cells']) / 2
        sv2_permeability        = 100 - sv2_wall_strength_index

        # --- SV3: Morphology & Gram Classification ---
        areas_um      = [r.area * PIXEL_AREA for r in valid_regions]
        circularities = [(4*np.pi*r.area)/(r.perimeter**2) if r.perimeter > 0 else 0 for r in valid_regions]
        aspect_ratios = [r.major_axis_length/r.minor_axis_length if r.minor_axis_length > 0 else 1 for r in valid_regions]
        roundnesses   = [(4*r.area)/(np.pi*r.major_axis_length**2) if r.major_axis_length > 0 else 1 for r in valid_regions]
        solidities    = [r.solidity for r in valid_regions]
        ferets        = [r.feret_diameter_max * PIXEL_SIZE for r in valid_regions]

        image_area_um = img_original.shape[0] * img_original.shape[1] * PIXEL_AREA
        debris_count = sum(1 for a in areas_um if a < 0.5)
        intact_count = n_valid - debris_count

        # Per-cell Gram classification using five-criterion voting classifier
        gram_pos = gram_neg = unclear = 0
        for region in valid_regions:
            cell_mask = masks == region.label
            cell_rgb = np.array([np.mean(red[cell_mask]), np.mean(green[cell_mask]), np.mean(blue[cell_mask])])
            g, _ = classify_gram_cell(cell_rgb, background_rgb)
            if g == 'gram_positive':   gram_pos += 1
            elif g == 'gram_negative': gram_neg += 1
            else:                      unclear  += 1

        sv3_mean_area = np.mean(areas_um)
        sv3_std_area  = np.std(areas_um)

        result = {
            'filename': img_name,
            # SV1
            'sv1_total_cells': n_cells, 'sv1_valid_cells': n_valid,
            'sv1_detection_rate': n_valid/n_cells*100 if n_cells > 0 else 0,
            'sv1_blue_mean': sv1_blue_mean, 'sv1_blue_std': sv1_blue_std,
            'sv1_blue_median': sv1_blue_median, 'sv1_blue_cv_pct': sv1_blue_cv_pct,
            'sv1_blue_min': sv1_blue_min, 'sv1_blue_max': sv1_blue_max,
            'sv1_red_mean': sv1_red_mean, 'sv1_red_std': sv1_red_std,
            'sv1_red_median': sv1_red_median, 'sv1_red_cv_pct': sv1_red_cv_pct,
            'sv1_red_min': sv1_red_min, 'sv1_red_max': sv1_red_max,
            'sv1_blue_red_ratio': sv1_blue_red_ratio,  # image-level mean, NOT classifier threshold
            'sv1_contrast_ratio': sv1_contrast_ratio,
            'sv1_color_separation': sv1_color_separation,
            'sv1_staining_quality': sv1_staining_quality,
            'sv1_dynamic_range': sv1_dynamic_range,
            'sv1_intensity_balance': sv1_intensity_balance,
            'sv1_blue_snr': sv1_blue_snr, 'sv1_red_snr': sv1_red_snr,
            'sv1_combined_snr': sv1_combined_snr,
            'sv1_signal_clarity': sv1_signal_clarity,
            'sv1_noise_ratio': sv1_noise_ratio,
            'sv1_blue_bg_mean': sv1_blue_bg_mean, 'sv1_blue_bg_std': sv1_blue_bg_std,
            'sv1_red_bg_mean': sv1_red_bg_mean, 'sv1_red_bg_std': sv1_red_bg_std,
            'sv1_bg_noise_level': sv1_bg_noise, 'sv1_bg_uniformity': sv1_bg_uniformity,
            # SV2 (imaging proxies)
            'sv2_texture_contrast': tex['mean_texture_contrast'],
            'sv2_texture_roughness': tex['mean_texture_roughness'],
            'sv2_texture_std': tex['std_texture_roughness'],
            'sv2_texture_uniformity': tex['texture_uniformity'],
            'sv2_texture_diversity': tex['texture_diversity'],
            'sv2_texture_range': tex['texture_range'],
            'sv2_edge_intensity': edg['mean_edge_intensity'],
            'sv2_edge_sharpness': edg['mean_edge_sharpness'],
            'sv2_edge_std': edg['std_edge_intensity'],
            'sv2_edge_uniformity': edg['edge_uniformity'],
            'sv2_boundary_contrast': edg['mean_boundary_contrast'],
            'sv2_wall_thickness_mean': wth['mean_wall_thickness_estimate'],
            'sv2_wall_thickness_median': wth['median_wall_thickness_estimate'],
            'sv2_wall_thickness_std': wth['std_wall_thickness'],
            'sv2_wall_thickness_cv': wth['cv_wall_thickness'],
            'sv2_wall_thickness_max': wth['max_wall_thickness'],
            'sv2_intensity_uniformity': mig['mean_intensity_uniformity'],
            'sv2_shape_regularity': mig['mean_shape_regularity'],
            'sv2_membrane_integrity_score': mig['membrane_integrity_score'],
            'sv2_pct_intact_cells': mig['pct_intact_cells'],
            'sv2_fragmentation_index': mig['fragmentation_index'],
            'sv2_cv_retention_mean': pep['mean_cv_retention'],
            'sv2_cv_retention_median': pep['median_cv_retention'],
            'sv2_cv_retention_std': pep['std_cv_retention'],
            'sv2_cv_retention_range': pep['cv_retention_range'],
            'sv2_peptidoglycan_score': pep['peptidoglycan_score'],
            'sv2_wall_quality_score': sv2_wall_quality_score,
            'sv2_wall_uniformity': sv2_wall_uniformity,
            'sv2_wall_strength_index': sv2_wall_strength_index,
            'sv2_permeability_estimate': sv2_permeability,
            # SV3 (voting classifier outputs)
            'sv3_total_cells': n_cells, 'sv3_valid_cells': n_valid,
            'sv3_cell_density_per_um2': n_valid / image_area_um,
            'sv3_cell_coverage_pct': sum(areas_um) / image_area_um * 100,
            'sv3_mean_area_um2': sv3_mean_area,
            'sv3_median_area_um2': np.median(areas_um),
            'sv3_std_area_um2': sv3_std_area,
            'sv3_cv_size_pct': sv3_std_area/sv3_mean_area*100 if sv3_mean_area > 0 else 0,
            'sv3_min_area_um2': np.min(areas_um), 'sv3_max_area_um2': np.max(areas_um),
            'sv3_size_range_um2': np.max(areas_um) - np.min(areas_um),
            'sv3_mean_circularity': np.mean(circularities),
            'sv3_std_circularity': np.std(circularities),
            'sv3_mean_roundness': np.mean(roundnesses),
            'sv3_mean_solidity': np.mean(solidities),
            'sv3_mean_aspect_ratio': np.mean(aspect_ratios),
            'sv3_std_aspect_ratio': np.std(aspect_ratios),
            'sv3_mean_feret_diam_um': np.mean(ferets),
            'sv3_pct_elongated_cells': sum(1 for ar in aspect_ratios if ar > 3) / len(aspect_ratios) * 100,
            'sv3_elongation_index': (np.mean(aspect_ratios) - 1) * 100,
            'sv3_shape_diversity': calculate_shannon_diversity(circularities),
            'sv3_size_heterogeneity': sv3_std_area/sv3_mean_area*100 if sv3_mean_area > 0 else 0,
            'sv3_morphology_score': (np.mean(circularities)+np.mean(roundnesses)+np.mean(solidities))/3,
            'sv3_uniformity_index': 100/(1+sv3_std_area/sv3_mean_area*100) if sv3_mean_area > 0 else 0,
            'sv3_lysis_pct': debris_count/n_valid*100 if n_valid > 0 else 0,
            'sv3_debris_count': debris_count, 'sv3_intact_count': intact_count,
            'sv3_gram_pos_count': gram_pos, 'sv3_gram_neg_count': gram_neg,
            'sv3_unclear_count': unclear,
            'sv3_gram_pos_pct': gram_pos/n_valid*100,
            'sv3_gram_neg_pct': gram_neg/n_valid*100,
            'sv3_gram_mixed_pct': unclear/n_valid*100,
            'bg_r': background_rgb[0], 'bg_g': background_rgb[1], 'bg_b': background_rgb[2]
        }
        return result
    except Exception as e:
        print(f"Error processing {img_name}: {e}")
        return None

# ============================================
# BATCH PROCESSING
# ============================================

all_results = []
for idx, img_path in enumerate(image_files):
    print(f"[{idx+1}/{len(image_files)}] {os.path.basename(img_path)}")
    result = analyze_image(img_path)
    if result: all_results.append(result)

# ============================================
# SAVE RESULTS
# ============================================

df = pd.DataFrame(all_results)
output_file = f'gram_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='Full_Data', index=False)
    for prefix, sheet in [('sv1_','SV1_Intensity_30vars'),
                           ('sv2_','SV2_CellWall_30vars'),
                           ('sv3_','SV3_Morphology_30vars')]:
        cols = ['filename'] + [c for c in df.columns if c.startswith(prefix)]
        df[cols].to_excel(writer, sheet_name=sheet, index=False)

files.download(output_file)
print(f"Done. {len(all_results)} images analysed.")
