console.log('[DEBUG] SCRIPT JS carregado');

const btnPreviewReport = document.getElementById('previewReport').addEventListener('click',previewReport);

function previewReport() {
    const form = document.getElementById('reportsForm'); // Alterado para 'reportsForm'
    console.log('ENTROU NA FUNÇÃO DE PREVIEW REPORT')
    const formData = new FormData(form);
    
    // Abre em nova aba
    const previewWindow = window.open('', '_blank');
    
    fetch('/reports/preview/pdf', {
        method: 'POST',
        body: formData
    })
    .then(response => response.text())
    .then(html => {
        previewWindow.document.write(html);
        previewWindow.document.close();
    })
    .catch(error => {
        console.error('Erro:', error);
        alert('Erro ao gerar visualização do relatório');
    });
}

// Adicione o evento para o botão de exportar Excel
document.getElementById('exportExcelBtn').addEventListener('click', function() {
    const form = document.getElementById('reportsForm');
    console.log('ENTROU NA FUNÇÃO DE EXPORTAR P/ EXCEL')

    form.action = "{{ url_for('export_excel') }}";
    form.submit();
});

console.log('%c[DEBUG] Sistema de proteção de status iniciado', 'color: green; font-weight: bold;');

document.addEventListener('DOMContentLoaded', () => {

    // Função para bloquear formulário
    function lockForm(form) {
        const select = form.querySelector('.status-select');
        const textarea = form.querySelector('textarea');
        const button = form.querySelector('.btn-update');
        
        if (select) select.disabled = true;
        if (textarea) {
            textarea.disabled = true;
            textarea.readOnly = true;
        }
        if (button) {
            button.disabled = true;
            button.classList.remove('btn-success');
            button.classList.add('btn-secondary');
            button.innerHTML = '<i class="bi bi-lock-fill"></i> Bloqueado';
        }
        
        console.log(`🔒 Formulário bloqueado para agendamento`);
    }

    // Processar formulários já bloqueados ao carregar
    document.querySelectorAll('.agendamento-form[data-is-locked="true"]').forEach(form => {
        lockForm(form);
    });

    // Interceptar mudanças de status
    document.querySelectorAll('.status-select').forEach(select => {
        const agendamentoId = select.dataset.agendamentoId;
        
        select.addEventListener('change', function(e) {
            const newStatus = this.value;
            const form = this.closest('form');
            const currentUserPerfil = '{{ current_user.perfil }}';
            
            console.log(`Status mudado para: ${newStatus} (Perfil: ${currentUserPerfil})`);
            
            // Se usuário da coordenação está mudando para "Apto-Coordenação"
            if (currentUserPerfil !== 'financeiro' && 
                currentUserPerfil !== 'admin' && 
                newStatus === 'Apto-Coordenação') {
                
                if (confirm('⚠️ ATENÇÃO: Ao marcar como "Apto-Coordenação", este agendamento será enviado para o Financeiro e você NÃO poderá mais editá-lo.\n\nDeseja continuar?')) {
                    console.log(`✅ Usuário confirmou mudança para Apto-Coordenação`);
                } else {
                    // Reverter para o valor anterior
                    this.value = this.defaultValue;
                    console.log(`❌ Usuário cancelou mudança para Apto-Coordenação`);
                }
            }
        });
    });

    // Interceptar submit dos formulários
    document.querySelectorAll('.agendamento-form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const isLocked = this.dataset.isLocked === 'true';
            
            if (isLocked) {
                e.preventDefault();
                alert('❌ Este agendamento está bloqueado pois já foi enviado para o Financeiro.');
                console.log('🚫 Tentativa de submit bloqueada');
                return false;
            }
            
            const select = this.querySelector('.status-select');
            const currentUserPerfil = '{{ current_user.perfil }}';
            
            if (select && select.value === 'Apto-Coordenação' && 
                currentUserPerfil !== 'financeiro' && 
                currentUserPerfil !== 'admin') {
                
                if (!confirm('⚠️ CONFIRMAÇÃO FINAL: Este agendamento será enviado para o Financeiro e você não poderá mais editá-lo.\n\nConfirma a atualização?')) {
                    e.preventDefault();
                    return false;
                }
            }
        });
    });

    console.log('%c[DEBUG] Sistema de proteção configurado com sucesso', 'color: blue; font-weight: bold;');
});

