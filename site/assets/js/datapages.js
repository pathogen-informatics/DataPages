(function () {
  function _valid_accession(accession) {
    var pattern = /^[A-Z]{3,4}\d{4,}$/;
    return pattern.test(accession);
  }

  function add_ena_links(table) {
    var column_indices = table.columns().eq(0);
    var number_of_columns = column_indices.length;
    var column_lookup = {}
    column_indices.each(function (index) {
      column_label = $(table.columns(index).header()).text();
      column_lookup[column_label] = index;
    });
    var study_idx = column_lookup['Study Accession']
    var run_idx = column_lookup['Run Accession']
    var sample_idx = column_lookup['Sample Accession']
    $('#data-table td').each(function (i, node) {
      row_idx = i % number_of_columns;
      if (row_idx == study_idx) {
        var study_accession = $(node).text();
        if (_valid_accession(study_accession)) {
          var study_url = "http://www.ebi.ac.uk/ena/data/view/"+study_accession;
          $(node).html('<a href="'+study_url+'">'+study_accession+'</a>');
        }
      } else if (row_idx == run_idx) {
        var run_accession = $(node).text();
        if (_valid_accession(run_accession)) {
          var run_url = "http://www.ebi.ac.uk/ena/data/view/"+run_accession;
          $(node).html('<a href="'+run_url+'">'+run_accession+'</a>');
        }
      } else if (row_idx == sample_idx) {
        var sample_accession = $(node).text();
        if (_valid_accession(sample_accession)) {
          var sample_url = "http://www.ebi.ac.uk/ena/data/view/"+sample_accession;
          $(node).html('<a href="'+sample_url+'">'+sample_accession+'</a>');
        }
      }
    });
  }

  function _show_spinner_hide_content(){
    $('#data-div').hide();
    $('#title').hide();
    $('#description').hide();
    $('#published_data_description').hide();
    $('#publications').hide();
    $('#links').hide();
    $('#wait-div').show();
  }

  function _show_content_hide_spinner(){
    $('#data-div').show();
    $('#title').show();
    $('#description').show();
    $('#published_data_description').show();
    $('#publications').show();
    $('#links').show();
    $('#wait-div').hide();
  }

  function _update_content(data) {
    var last_updated = new Date(data['updated']);
    $('#data-updated').text("Last updated: "+last_updated);

    var title = '<h2>' + data['species'] + '</h2>'
    $('#title').html(title);

    var description = data['description'];
    $('#description').html(description);

    var published_data_description = data['published_data_description'];
    $('#published_data_description').html(published_data_description);

    var links = data['links'];
    $('#links').html(links);

    var pubmed_ids = data['pubmed_ids'];
    var backup_pubmedid_rendering = function() {
      $('#publications').empty();
      $('#publications').append($('<h3>Publications</h3>'));
      var publication_list = $('<ul></ul>');
      $.each(pubmed_ids, function(_, pubmed_id) {
        publication_list.append($('<li><a href="http://europepmc.org/abstract/MED/'+pubmed_id+'">'+pubmed_id+'</a></li>'));
      });
      $('#publications').append(publication_list);
    };
    if (pubmed_ids.length) {
      $.ajax({
        url: "/component/References?pars=" + pubmed_ids.join(" "),
        success: function(result) {
          if (result.length > 0) {
            $('#publications').empty();
            $('#publications').append($('<h3>Publications</h3>'));
            $('#publications').append($(result));
          } else {
            backup_pubmedid_rendering()
          }
        },
        error: backup_pubmedid_rendering,
      });
    } else {
      $('#publications').empty();
    }
  }

  function _show_table_and_project_list() {
    $('#data-div').show();
    $('#projects').show();
  }

  function _hide_table_and_project_list() {
    $('#data-div').hide();
    $('#projects').hide();
  }

  function _number_of_rows(table) {
    return table.rows().data().length
  }

  function update_table_for_species(table, species, project) {
    _show_spinner_hide_content();
    var data_url = get_species_urls()[species];
    $('#species_selector').text(species);
    var current_species = $('#species_selector').data('species');
    if (current_species && current_species == species) {
      _show_content_hide_spinner();
      if (_number_of_rows(table) == 0) {
        _hide_table_and_project_list();
      } else {
        update_project_lists_from_table(table, species, project);
        _show_table_and_project_list();
      }
    } else if (data_url && table.ajax.url(data_url)) {
      table.load(function (data) {
        var new_columns = data['columns'];
        var column_lookup = {};
        new_columns.forEach((name, index) => $(table.columns(index).header()).text(name));

        _update_content(data)
        _show_content_hide_spinner();
        $('#species_selector').data('species', species);
        if (_number_of_rows(table) == 0) {
          _hide_table_and_project_list();
        } else {
          update_project_lists_from_table(table, species, project);
          add_ena_links(table);
          _show_table_and_project_list();
        }
      });
      $("#data-table").on('draw.dt', function() {
        add_ena_links(table);
      });
    } else {
      // There was an issue updating the table, maybe the species doesn't exist
      table.clear();
      _show_content_hide_spinner();
      $('#species_selector').data('species', species);
      update_project_lists_from_table(table, species, 'All Projects');
    }
  }

  function update_project_lists_from_table(table, species, default_project) {
    table.column(1).search('').draw();
    $('#project_selector').text(default_project);
    var projects = table.column(1).data().unique().sort();
    var project_list = $('#project_list');
    project_list.empty();
    project_list.append('<li><a href="#">All Projects</a></li>');
    projects.each ( function (d) {
      project_list.append('<li><a href="#">' + d + '</a></li>');
    });
    filter_by_project(table, default_project);
    $("#project_list a").click(function (event) {
      event.preventDefault();
      var project = $(this).text();
      $('#project_selector').text(project);
      filter_by_project(table, project);
      update_url_params(species, project, true);
    });
  }

  function filter_by_project(table, project) {
    if (project == 'All Projects') {
      table.column(1).search('').draw();
    } else {
      table.column(1).search('^' + $.fn.dataTable.util.escapeRegex(project) + '$', true, false).draw();
    }
  }

  function get_url_params() {
    var param_string = location.search.substring(1);
    var key_value_pairs = param_string.split('&');
    var key_values_list = key_value_pairs.map( function (kv) { return kv.split('=').map( decodeURIComponent ) } );
    var params = {}
    key_values_list.forEach( function ( key_value) { key = key_value[0]; value = key_value[1]; params[key] = value });
    return params;
  }

  function get_species_urls() {
    var links = {};
    $('#species_list a').each( function () {
      var species = $(this).text();
      var url = $(this).attr('href');
      links[species] = url;
    });
    return links;
  }

  function update_url_params(species, project, push_state) {
    var param_string = '?species=' + encodeURIComponent(species);
    if (project) {
      param_string += '&project=' + encodeURIComponent(project);
    }
    var path = location.pathname + param_string
    var state = {
      'species': species,
      'project': project
    };
    if (push_state) {
      history.pushState(state, species, path);
    } else {
      history.replaceState(state, species, path);
    }
  }

  window.onpopstate = function(event) {
    var state = event.state;
    var species = state['species'];
    var project = state['project'];
    var table = $("#data-table").DataTable();
    update_table_for_species(table, species, project);
  };

  $(document).ready(function() {
    var params = get_url_params()
    var first_species=$('#species_list a').first().text();
    var species = params['species'] || first_species;
    var project = params['project'] || 'All Projects';
    var table = $("#data-table").DataTable();
    update_table_for_species(table, species, project);
    update_url_params(species, project, false);
    $('#species_list a').click(function (event){
      event.preventDefault();
      var species = $(this).text();
      update_table_for_species(table, species, 'All Projects');
      update_url_params(species, 'All Projects', true);
    });
  });
})();
