-- Debe devolver cero filas antes de exigir el alias global único.
select lower(btrim(usuario)) as usuario_repetido, count(*) as cantidad
from public.usuarios
where usuario is not null
  and btrim(usuario) <> ''
group by lower(btrim(usuario))
having count(*) > 1
order by usuario_repetido;
