<?php
$post = get_page_by_path('customer-dropbox', OBJECT, 'cuar_private_file');
if (!$post) {
    require '/challenge/seed.php';
    return;
}

$files = get_post_meta($post->ID, 'cuar_private_file_file', true);
if (is_array($files)) {
    $po = cuar_addon('post-owner');
    foreach ($files as $file) {
        if (($file['source'] ?? '') !== 'local' || empty($file['file'])) {
            continue;
        }
        $path = $po->get_private_file_path($file['file'], $post->ID, false);
        if (is_file($path)) {
            unlink($path);
        }
    }
}
delete_post_meta($post->ID, 'cuar_private_file_file');
require '/challenge/seed.php';
