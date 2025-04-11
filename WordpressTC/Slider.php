<?php
// Include scripts
require_once get_template_directory() . '/inc/admin.php';
require_once get_template_directory() . '/inc/author.php';
require_once get_template_directory() . '/inc/ad_banners.php';
require_once get_template_directory() . '/inc/category.php';
require_once get_template_directory() . '/inc/custom_blocks.php';
require_once get_template_directory() . '/inc/enqueue_scripts.php';
require_once get_template_directory() . '/inc/filters.php';
require_once get_template_directory() . '/inc/global.php';
require_once get_template_directory() . '/inc/helpers.php';
require_once get_template_directory() . '/inc/menu.php';
require_once get_template_directory() . '/inc/post.php';
require_once get_template_directory() . '/inc/search.php';
require_once get_template_directory() . '/inc/sharing.php';
require_once get_template_directory() . '/inc/tag.php';
require_once get_template_directory() . '/inc/redirect404.php';

// Ajouter un shortcode pour la grille magazine Numéro avec effet de défilement et blocage temporaire du scroll
function slider_pablo_shortcode($atts) {
    $atts = shortcode_atts(array(
        'category' => '',
        'tag' => '',
        'count' => 5,
        'offset' => 0,
        'post_ids' => '',
        'exclude' => '',
    ), $atts);

    ob_start();
    $unique_id = 'numero-grid-' . uniqid();
    ?>
    <style>
    .numero-container {
      display: grid;
      grid-template-columns: minmax(400px, 5fr) minmax(400px, 7fr);
      gap: 20px;
      max-width: 2000px;
      margin: 0 auto;
      padding: 20px;
      margin-bottom: 70px;
      position: relative;
    }
    .numero-main {
      grid-column: 1;
      position: relative;
      border-radius: 8px;
      overflow: hidden;
      height: 1200px;
    }
    .numero-right {
      grid-column: 2;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      height: 1200px;
      overflow: hidden;
      position: relative;
    }
    .numero-col-1, .numero-col-2 {
      position: relative;
      will-change: transform;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .numero-item {
      position: relative;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 3px 8px rgba(0,0,0,0.1);
      flex-shrink: 0;
      min-height: 450px;
    }
    .numero-item img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      transition: transform 0.4s;
    }
    .numero-item:hover img {
      transform: scale(1.03);
    }
    .numero-overlay {
      position: absolute;
      bottom: 0;
      left: 0;
      width: 100%;
      padding: 30px;
      background: linear-gradient(to top, rgba(0,0,0,0.8), rgba(0,0,0,0.2), transparent);
      color: white;
      z-index: 2;
    }
    .numero-date {
      position: absolute;
      top: 10px;
      right: 10px;
      font-size: 11px;
      color: white;
      z-index: 2;
      background-color: rgba(0,0,0,0.5);
      padding: 3px 8px;
      border-radius: 3px;
    }
    .numero-category {
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 5px;
    }
    .numero-title {
      font-size: 18px;
      font-weight: 500;
      line-height: 1.3;
      margin: 0;
    }
    .numero-main .numero-title {
      font-size: 26px;
      max-width: 90%;
    }
    .numero-title a {
      color: white;
      text-decoration: none;
    }
    .numero-title a:hover {
      text-decoration: underline;
    }
    @media (max-width: 1024px) {
      .numero-container {
        grid-template-columns: 1fr;
        max-width: 100%;
        padding: 0;
      }
      .numero-main {
        height: 800px;
        width: 100%;
      }
      .numero-right {
        grid-column: 1;
        grid-row: 2;
        height: auto;
        gap: 15px;
      }
      .numero-col-1 .numero-item,
      .numero-col-2 .numero-item {
        height: 500px;
      }
    }
    @media (max-width: 768px) {
      .numero-right {
        grid-template-columns: 1fr;
      }
      .numero-main {
        height: 700px;
      }
    }
    </style>

    <div class="numero-container" id="<?php echo $unique_id; ?>">
      <?php
      // Augmenter le nombre d'articles pour éviter les espaces blancs
      $count_requested = intval($atts['count']);
      $count_actual = max($count_requested, 9); // Au moins 9 articles pour éviter les espaces blancs
      
      $args = array(
        'post_type' => 'post',
        'posts_per_page' => $count_actual,
        'orderby' => 'date',
        'order' => 'DESC',
        'offset' => intval($atts['offset']),
      );

      if (!empty($atts['category'])) {
        $args['category_name'] = $atts['category'];
      }
      if (!empty($atts['tag'])) {
        $args['tag'] = $atts['tag'];
      }
      if (!empty($atts['post_ids'])) {
        $args['post__in'] = explode(',', $atts['post_ids']);
        $args['orderby'] = 'post__in';
      }
      if (!empty($atts['exclude'])) {
        $args['post__not_in'] = explode(',', $atts['exclude']);
      }

      $query = new WP_Query($args);
      $posts = [];
      if ($query->have_posts()) {
        while ($query->have_posts()) {
          $query->the_post();
          $posts[] = [
            'title' => get_the_title(),
            'permalink' => get_permalink(),
            'img' => has_post_thumbnail() ? get_the_post_thumbnail_url(get_the_ID(), 'full') : get_template_directory_uri() . '/assets/images/placeholder.jpg',
            'alt' => get_the_title(),
            'date' => str_replace(
              ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
              ['jan', 'fév', 'mar', 'avr', 'mai', 'juin', 'juil', 'août', 'sep', 'oct', 'nov', 'déc'],
              get_the_date('j M Y')
            ),
            'cat' => ($cats = get_the_category()) ? strtoupper($cats[0]->name) : 'CINÉMA'
          ];
        }
        wp_reset_postdata();
      }
      
      // Si pas assez d'articles, dupliquer les derniers pour éviter les espaces blancs
      $min_articles_needed = 9; // 1 principal + 4 dans chaque colonne
      if (count($posts) < $min_articles_needed) {
        $original_count = count($posts);
        if ($original_count > 0) {
          // Dupliquer les articles existants jusqu'à atteindre le minimum requis
          for ($i = 0; $i < ($min_articles_needed - $original_count); $i++) {
            $index = $i % $original_count;
            $posts[] = $posts[$index];
          }
        }
      }
      ?>

      <?php if (!empty($posts)) : ?>
        <article class="numero-main numero-item">
          <img src="<?php echo esc_url($posts[0]['img']); ?>" alt="<?php echo esc_attr($posts[0]['alt']); ?>">
          <div class="numero-date"><?php echo $posts[0]['date']; ?></div>
          <div class="numero-overlay">
            <div class="numero-category"><?php echo $posts[0]['cat']; ?></div>
            <h2 class="numero-title"><a href="<?php echo esc_url($posts[0]['permalink']); ?>"><?php echo esc_html($posts[0]['title']); ?></a></h2>
          </div>
        </article>
        <div class="numero-right">
          <div class="numero-col-1">
            <?php
            // Modifier la répartition pour avoir au moins 4 articles par colonne
            $remaining = count($posts) - 1; // Moins l'article principal
            $per_column = max(4, ceil($remaining / 2)); // Au moins 4 articles par colonne
            
            foreach ($posts as $index => $p) : 
              if ($index > 0 && $index <= $per_column) : // Première colonne 
            ?>
              <article class="numero-item">
                <img src="<?php echo esc_url($p['img']); ?>" alt="<?php echo esc_attr($p['alt']); ?>">
                <div class="numero-date"><?php echo $p['date']; ?></div>
                <div class="numero-overlay">
                  <div class="numero-category"><?php echo $p['cat']; ?></div>
                  <h2 class="numero-title"><a href="<?php echo esc_url($p['permalink']); ?>"><?php echo esc_html($p['title']); ?></a></h2>
                </div>
              </article>
            <?php endif; endforeach; ?>
          </div>
          <div class="numero-col-2">
            <?php foreach ($posts as $index => $p) : 
              if ($index > $per_column) : // Deuxième colonne
            ?>
              <article class="numero-item">
                <img src="<?php echo esc_url($p['img']); ?>" alt="<?php echo esc_attr($p['alt']); ?>">
                <div class="numero-date"><?php echo $p['date']; ?></div>
                <div class="numero-overlay">
                  <div class="numero-category"><?php echo $p['cat']; ?></div>
                  <h2 class="numero-title"><a href="<?php echo esc_url($p['permalink']); ?>"><?php echo esc_html($p['title']); ?></a></h2>
                </div>
              </article>
            <?php endif; endforeach; ?>
          </div>
        </div>
      <?php else : ?>
        <p>Aucun article trouvé.</p>
      <?php endif; ?>
    </div>

    <script>
document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('<?php echo $unique_id; ?>');
    const col1 = container.querySelector('.numero-col-1');
    const col2 = container.querySelector('.numero-col-2');
    const mainImage = container.querySelector('.numero-main');
    let scrollY1 = 0;
    let scrollY2 = 0;
    let isSliderScrolling = false;
    let lastScrollY1 = 0;
    let lastScrollY2 = 0;

    if (!col1 || !col2 || !mainImage) return;

    // Initialiser le Scroll Infini
    function initScrollInfinite() {
        // Calculer le point d'arrêt (milieu de l'image principale)
        const mainImageHeight = mainImage.offsetHeight;
        const midpointMainImage = mainImageHeight / 2;
        
        // Calculer la hauteur maximale de défilement pour avoir toujours des articles visibles
        const col1Items = col1.querySelectorAll('.numero-item');
        const col2Items = col2.querySelectorAll('.numero-item');
        
        // Hauteur d'un article (supposée être la même pour tous)
        let itemHeight = 0;
        if (col1Items.length > 0) {
            itemHeight = col1Items[0].offsetHeight;
        }
        
        // Calculer les limites de défilement pour toujours avoir 1-2 articles visibles
        const col1Max = Math.max(0, col1.scrollHeight - itemHeight * 2);
        const col2Max = Math.max(0, col2.scrollHeight - itemHeight * 2);

        window.addEventListener('wheel', function (e) {
            if (isSliderScrolling) {
                e.preventDefault(); // Empêche le scroll de la page

                // Calcul du scroll dans le slider
                const scrollAmount = e.deltaY * 1.1; // ajuster la vitesse de défilement

                // Récupérer les positions actuelles des articles visibles dans chaque colonne
                
                // Appliquer le scroll seulement si aucun article n'est aligné avec le milieu de l'image principale
                let shouldScroll = true;
                
                // Vérifier si un élément de col1 est au milieu de l'image principale
                col1Items.forEach(item => {
                    const itemRect = item.getBoundingClientRect();
                    const mainRect = mainImage.getBoundingClientRect();
                    
                    // Position relative par rapport au haut de l'image principale
                    const itemRelativeTop = itemRect.top - mainRect.top;
                    
                    // Si l'élément est proche du milieu de l'image principale et qu'on défile vers le bas
                    if (Math.abs(itemRelativeTop - midpointMainImage) < 20 && scrollAmount > 0) {
                        shouldScroll = false;
                    }
                });
                
                // Vérifier si un élément de col2 est au milieu de l'image principale
                col2Items.forEach(item => {
                    const itemRect = item.getBoundingClientRect();
                    const mainRect = mainImage.getBoundingClientRect();
                    
                    // Position relative par rapport au haut de l'image principale
                    const itemRelativeTop = itemRect.top - mainRect.top;
                    
                    // Si l'élément est proche du milieu de l'image principale et qu'on défile vers le bas
                    if (Math.abs(itemRelativeTop - midpointMainImage) < 20 && scrollAmount > 0) {
                        shouldScroll = false;
                    }
                });

                if (shouldScroll) {
                    // Applique le scroll dans les deux colonnes
                    scrollY1 += scrollAmount;
                    scrollY2 += scrollAmount;

                    // Limites de scroll dans chaque colonne pour toujours garder des articles visibles
                    scrollY1 = Math.max(0, Math.min(scrollY1, col1Max));
                    scrollY2 = Math.max(0, Math.min(scrollY2, col2Max));

                    // Applique la transformation de défilement
                    col1.style.transform = `translateY(${-scrollY1}px)`;
                    col2.style.transform = `translateY(${-scrollY2}px)`;
                }

                // Vérifie si le slider a atteint sa fin ou le début
                if ((scrollY1 >= col1Max - 10 && scrollY2 >= col2Max - 10) || (scrollY1 <= 0 && scrollY2 <= 0)) {
                    if (lastScrollY1 !== scrollY1 || lastScrollY2 !== scrollY2) {
                        isSliderScrolling = false;
                        document.body.style.overflow = 'auto'; // Réactive le scroll global
                    }
                }

                // Stocker les dernières positions de scroll pour comparer
                lastScrollY1 = scrollY1;
                lastScrollY2 = scrollY2;
            }
        }, { passive: false });
    }

    const images = container.querySelectorAll('img');
    let loaded = 0;
    images.forEach(img => {
        if (img.complete) loaded++;
        else img.addEventListener('load', () => {
            loaded++;
            if (loaded === images.length) initScrollInfinite();
        });
    });
    if (loaded === images.length) initScrollInfinite();

    // Intersection Observer pour détecter quand le slider devient visible
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // Quand le slider devient visible, activer le scroll pour le slider
                enableScrollForSlider();
            } else {
                // Si le slider n'est plus visible, désactiver le scroll pour le slider
                disableScrollForSlider();
            }
        });
    }, { threshold: 0.5 }); // Observer dès 50% de visibilité

    observer.observe(container); // Observer l'élément container du slider

    function enableScrollForSlider() {
        isSliderScrolling = true;
        document.body.style.overflow = 'hidden'; // Désactive le scroll global
    }

    function disableScrollForSlider() {
        isSliderScrolling = false;
        document.body.style.overflow = 'auto'; // Réactive le scroll global
    }
});
</script>

    <?php
    return ob_get_clean();
}
add_shortcode('slider_pablo', 'slider_pablo_shortcode');