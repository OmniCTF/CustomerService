<?php
// Idempotent content/capability seeding. This file does not handle HTTP requests.

// Complete the plugin's legitimate first-run state so low-privilege requests are
// not redirected to the administrator-only setup wizard.
$installer = cuar_addon('installer');
$installer->set_installed();
$installer->set_pending_redirect('');
update_option('cuar_deferred_actions', []);
$customer_pages = cuar_addon('customer-pages');
$customer_pages->create_all_missing_pages();
cuar()->update_option(CUAR_Settings::$OPTION_CURRENT_VERSION, CUAR_PLUGIN_VERSION);
update_option('cuar_deferred_actions', []);

$username = getenv('PLAYER_USER') ?: 'customer';
$password = getenv('PLAYER_PASSWORD') ?: 'customer-local-only';
$user = get_user_by('login', $username);

if (!$user) {
    $user_id = wp_create_user($username, $password, 'customer@example.test');
    if (is_wp_error($user_id)) {
        throw new RuntimeException($user_id->get_error_message());
    }
    $user = get_user_by('id', $user_id);
} else {
    wp_set_password($password, $user->ID);
}

$role = get_role('customer_area_player');
if (!$role) {
    $role = add_role('customer_area_player', 'Customer Area Player', ['read' => true]);
}

// Minimal primitives needed to open and read the player's own private-file post.
foreach (['read', 'cuar_pf_edit', 'cuar_pf_read'] as $capability) {
    $role->add_cap($capability);
}
foreach (['cuar_access_admin_panel', 'cuar_pf_manage_attachments', 'cuar_pf_list_all', 'cuar_pf_delete'] as $capability) {
    $role->remove_cap($capability);
}
$user->set_role('customer_area_player');

$existing = get_page_by_path('customer-dropbox', OBJECT, 'cuar_private_file');
if (!$existing) {
    $post_id = wp_insert_post([
        'post_type' => 'cuar_private_file',
        'post_status' => 'publish',
        'post_title' => 'Customer document dropbox',
        'post_name' => 'customer-dropbox',
        'post_content' => 'Upload and retrieve documents assigned to your customer account.',
        'post_author' => $user->ID,
    ], true);
    if (is_wp_error($post_id)) {
        throw new RuntimeException($post_id->get_error_message());
    }
} else {
    $post_id = $existing->ID;
    wp_update_post(['ID' => $post_id, 'post_author' => $user->ID, 'post_status' => 'publish']);
}

$home = get_page_by_path('portal-home', OBJECT, 'page');
$home_content = '<h2>Northstar customer portal</h2>'
    . '<p>Use your supplied customer account to manage documents in your private dropbox.</p>'
    . '<p><a href="' . esc_url(admin_url('post.php?post=' . $post_id . '&action=edit')) . '">Manage my document dropbox</a></p>';

if (!$home) {
    $home_id = wp_insert_post([
        'post_type' => 'page', 'post_status' => 'publish', 'post_title' => 'Customer Portal',
        'post_name' => 'portal-home', 'post_content' => $home_content,
    ]);
} else {
    $home_id = $home->ID;
    wp_update_post(['ID' => $home_id, 'post_content' => $home_content, 'post_status' => 'publish']);
}

update_option('show_on_front', 'page');
update_option('page_on_front', (int) $home_id);
update_option('blogdescription', 'Secure document exchange for Northstar customers');
update_option('users_can_register', 0);
echo "Seeded customer user and private file post ID {$post_id}.\n";
