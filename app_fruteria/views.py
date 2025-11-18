# app_fruteria/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages 
from django.contrib.auth.forms import AuthenticationForm
import datetime 
from .forms import RegistroClienteForm
from django.http import JsonResponse

# ====================================================================
# CORRECCIÓN: Importación de TODOS los Modelos de la App
# ====================================================================
from .models import (
    Producto, 
    Categoria, 
    Oferta, 
    PerfilCliente, 
    Sucursal,       # <-- Nuevo
    Compra,         # <-- Nuevo
    DetalleCompra   # <-- Nuevo
)
from django.db.models import Q 

# --------------------------------------------------------------------------
# A. VISTAS DEL CATÁLOGO Y HOME
# --------------------------------------------------------------------------

def index(request):
    """
    Vista para la página principal (index.html).
    """
    productos_destacados = Producto.objects.all().order_by('-id')[:3] 
    
    contexto = {
        'productos_destacados': productos_destacados
    }
    return render(request, 'app_fruteria/index.html', contexto)

def menu_virtual(request):
    """
    Muestra el catálogo completo de productos (menu.html).
    """
    productos = Producto.objects.all().order_by('nombre')
    
    contexto = {
        'lista_productos': productos
    }
    return render(request, 'app_fruteria/menu.html', contexto)

def frutas_citricas(request):
    """
    Muestra solo las frutas de la categoría 'Cítricas' (citricas.html).
    """
    try:
        productos = Producto.objects.filter(categoria__nombre='Cítricas').order_by('nombre')
    except:
        productos = Producto.objects.none()

    contexto = {
        'lista_productos': productos,
        'nombre_seccion': 'Frutas Cítricas'
    }
    return render(request, 'app_fruteria/citricas.html', contexto)

def frutas_dulces(request):
    """
    Muestra solo las frutas de la categoría 'Dulces' (dulces.html).
    """
    try:
        productos = Producto.objects.filter(categoria__nombre='Dulces').order_by('nombre')
    except:
        productos = Producto.objects.none() 

    contexto = {
        'lista_productos': productos,
        'nombre_seccion': 'Frutas Dulces'
    }
    return render(request, 'app_fruteria/dulces.html', contexto)

def frutas_neutras(request):
    """
    Muestra solo las frutas de la categoría 'Neutras' (neutras.html).
    """
    try:
        productos = Producto.objects.filter(categoria__nombre='Neutras').order_by('nombre')
    except:
        productos = Producto.objects.none() 

    contexto = {
        'lista_productos': productos,
        'nombre_seccion': 'Frutas Neutras'
    }
    return render(request, 'app_fruteria/neutras.html', contexto)

def ver_ofertas(request):
    """
    Muestra todos los productos que están asignados a ofertas activas y vigentes.
    """
    hoy = datetime.date.today()
    
    
    lista_productos_oferta = Producto.objects.filter(
        oferta__isnull=False,
        oferta__fecha_inicio__lte=hoy, 
        oferta__fecha_fin__gte=hoy
    ).order_by('nombre')

    # Solo enviamos la lista de productos
    contexto = {
        'lista_productos': lista_productos_oferta, # Cambiamos el nombre de la variable para que coincida con la plantilla
        'titulo_seccion': ' Ofertas y Promociones Vigentes'
    }

    
    return render(request, 'app_fruteria/ofertas.html', contexto)


# --------------------------------------------------------------------------
# B. VISTAS DE AUTENTICACIÓN
# --------------------------------------------------------------------------


def registro_usuario(request):
    """
    Maneja el registro de nuevos usuarios (inicios.html) usando un formulario seguro.
    """
    next_url = request.GET.get('next')  # Se define arriba para que esté disponible siempre

    if request.method == 'POST':
        form = RegistroClienteForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)

            messages.success(request, '¡Cuenta creada y sesión iniciada! Bienvenido a Olivos Verdes.')

            fallback_redirect = 'compra'  # Redirección por defecto
            return redirect(request.POST.get('next') or next_url or fallback_redirect)

        else:
            messages.error(request, 'Error en el registro. Por favor, verifica los datos.')
    else:
        form = RegistroClienteForm()

    contexto = {
        'form': form,
        'next': next_url
    }

    return render(request, 'app_fruteria/inicios.html', contexto)

def iniciar_sesion(request):
    """
    Maneja el inicio de sesión de usuarios existentes (login.html).
    """
    if request.method == 'POST':
        # AuthenticationForm es el formulario estándar de Django para login
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            # Autenticación real contra la base de datos
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'¡Bienvenido de nuevo! Sesión iniciada.')
                
                # Manejo de redirección. Si el usuario intentó comprar (que usa @login_required),
                # Django añade ?next=/confirmar_compra/ a la URL. 
                # Esto lo redirige de vuelta a la compra.
                return redirect(request.POST.get('next') or 'menu_virtual')
            else:
                messages.error(request, 'Usuario o contraseña incorrectos.')
        else:
             messages.error(request, 'Usuario o contraseña incorrectos.')
    
    # Si la petición es GET o si el login falló
    form = AuthenticationForm()
    contexto = {'form': form}
    return render(request, 'app_fruteria/login.html', contexto)


@login_required 
def perfil_usuario(request):
    """ Muestra la información del usuario logueado (perfil.html). """
    # Esta parte es correcta y asume que el PerfilCliente existe (creado en registro_usuario)
    try:
        perfil = request.user.perfilcliente 
    except PerfilCliente.DoesNotExist:
        perfil = None 
        
    contexto = {
        'perfil': perfil,
        'usuario': request.user # También pasamos el objeto User
    }
    return render(request, 'app_fruteria/perfil.html', contexto)

def cerrar_sesion(request):
    """ Cierra la sesión del usuario. """
    logout(request)
    messages.success(request, 'Has cerrado sesión correctamente.')
    return redirect('inicio')


# --------------------------------------------------------------------------
# C. VISTAS DEL CARRITO Y COMPRA (Lógica con Sesiones de Django)
# --------------------------------------------------------------------------

def agregar_al_carrito(request, producto_id):
    """ 
    Añade un producto al carrito, aplicando el precio final (con descuento).
    """
    producto = get_object_or_404(Producto, pk=producto_id)
    carrito = request.session.get('carrito', {})
    producto_id_str = str(producto_id)
    
    # 🚨 CLAVE DE CORRECCIÓN: Usar la propiedad .precio_final para aplicar la oferta 🚨
    precio_a_guardar = str(producto.precio_final)
    
    if producto_id_str in carrito:
        carrito[producto_id_str]['cantidad'] += 1
        cantidad_actual = carrito[producto_id_str]["cantidad"]
        # OPCIONAL: Actualizar el precio si la oferta cambió mientras estaba en el carrito
        carrito[producto_id_str]['precio'] = precio_a_guardar 
    else:
        carrito[producto_id_str] = {
            'cantidad': 1,
            'precio': precio_a_guardar # <-- Guarda el precio con descuento
        }
        cantidad_actual = 1
        
    request.session['carrito'] = carrito
    request.session.modified = True # Asegura que la sesión se guarde
    
    # --- LÓGICA DE RESPUESTA ---
    mensaje = f'✅ ¡{producto.nombre} añadido! Cantidad total: {cantidad_actual} kg.'
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest': 
        return JsonResponse({ 
            'success': True,
            'message': mensaje,
            # No es necesario devolver totales aquí, pero sí en eliminar/ajustar
        })
    
    messages.success(request, mensaje)
    return redirect(request.META.get('HTTP_REFERER') or 'menu_virtual')

def ver_carrito(request):
    """
    Muestra los productos en el carrito (carrito.html) y calcula totales.
    """
    carrito = request.session.get('carrito', {})
    carrito_items = []
    total_general = 0
    costo_envio = 40.00 # Define el costo de envío
    
    for id_str, data in carrito.copy().items():
        try:
            producto = Producto.objects.get(pk=int(id_str))
            cantidad = data.get('cantidad', 0)
            precio = float(data.get('precio', 0))
            
            subtotal = cantidad * precio
            total_general += subtotal
            
            carrito_items.append({
                'producto': producto,
                'cantidad': cantidad,
                'subtotal': subtotal,
                'precio_unitario': precio, 
            })
            
        except Producto.DoesNotExist:
            del carrito[id_str]
            request.session.modified = True 
        except ValueError:
            del carrito[id_str]
            request.session.modified = True
            messages.error(request, f"Error en el formato del precio del producto ID {id_str}. Eliminado del carrito.")

    request.session['carrito'] = carrito

    total_final = total_general + costo_envio

    contexto = {
        'carrito_items': carrito_items,
        'total_general': total_general,
        'costo_envio': costo_envio,
        'total_final': total_final, 
    }
    
    return render(request, 'app_fruteria/carrito.html', contexto)

def ajustar_cantidad(request, producto_id, accion):
    
    carrito = request.session.get('carrito', {})
    producto_id_str = str(producto_id)
    
    if producto_id_str in carrito:
        cantidad_actual = carrito[producto_id_str]['cantidad']
        
        # OPCIONAL: Previene que el precio de oferta se pierda si la sesión es reescrita
        # Recuperamos el precio actual de la sesión (con descuento)
        precio_guardado = carrito[producto_id_str]['precio'] 
        
        if accion == 'aumentar':
            carrito[producto_id_str]['cantidad'] = cantidad_actual + 1
            messages.success(request, f"Cantidad de producto ID {producto_id} aumentada.")
            
        elif accion == 'disminuir':
            if cantidad_actual > 1:
                carrito[producto_id_str]['cantidad'] = cantidad_actual - 1
                messages.success(request, f"Cantidad de producto ID {producto_id} disminuida.")
            else:
                # Si la cantidad es 1 y se intenta disminuir, se elimina el ítem
                del carrito[producto_id_str]
                messages.info(request, f"Producto ID {producto_id} eliminado del carrito.")
                
        # Aseguramos que el precio de oferta original se mantenga en la sesión
        carrito[producto_id_str]['precio'] = precio_guardado

        # Guardar los cambios
        request.session['carrito'] = carrito
        request.session.modified = True 
        
    return redirect('ver_carrito')

@login_required 
def confirmar_compra(request):
    """ Muestra el resumen de compra y procesa el pago (compra.html). """
    carrito = request.session.get('carrito', {})
    carrito_items = []
    total_general = 0
    
    if not carrito:
        messages.warning(request, "No puedes confirmar la compra con un carrito vacío.")
        return redirect('menu_virtual')

    # Recalcular ítems y total general (misma lógica que ver_carrito)
    for id_str, data in carrito.items():
        producto = get_object_or_404(Producto, pk=int(id_str))
        cantidad = data['cantidad']
        precio = float(data['precio'])
        subtotal = cantidad * precio
        total_general += subtotal
        
        carrito_items.append({
            'producto': producto,
            'cantidad': cantidad,
            'subtotal': subtotal,
        })
    
    # Lógica de POST: Procesamiento de pago
    if request.method == 'POST':
        # Aquí iría la lógica de transacción y creación de objetos Compra y DetalleCompra en DB
        
        # 1. Crear el objeto Compra (cabecera)
        # 2. Crear los objetos DetalleCompra (ítems del carrito)
        # 3. Limpiar el carrito de la sesión
        del request.session['carrito']
        
        messages.success(request, '¡Compra realizada con éxito! Recibirás la confirmación en tu correo.')
        return redirect('inicio') # Redirigir al inicio o a una página de agradecimiento
        
    # Lógica de GET: Mostrar el resumen para confirmación
    try:
        perfil = request.user.perfilcliente 
    except PerfilCliente.DoesNotExist:
        perfil = None 
    
    contexto = {
        'carrito_items': carrito_items,
        'total_general': total_general,
        'perfil': perfil,
        'usuario': request.user # Para usar el nombre en el template
    }
    return render(request, 'app_fruteria/compra.html', contexto)
def eliminar_item_carrito(request, producto_id):
    """
    Elimina un producto del carrito, recalcula los totales y responde con JSON
    si es una solicitud AJAX para la actualización suave de la interfaz.
    """
    carrito = request.session.get('carrito', {})
    producto_id_str = str(producto_id)
    producto_nombre = "Producto"
    costo_envio = 40.00 # Definimos el costo de envío aquí

    try:
        # Recuperamos el nombre del producto solo para el mensaje
        producto = Producto.objects.get(pk=producto_id)
        producto_nombre = producto.nombre
    except Producto.DoesNotExist:
        pass

    if producto_id_str in carrito:
        # 1. Eliminar el producto del diccionario
        del carrito[producto_id_str]
        request.session.modified = True
        
        mensaje = f'🗑️ {producto_nombre} ha sido eliminado de tu carrito.'
        
        # --- LÓGICA DE RESPUESTA AJAX ---
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            
            # 2. Recalcular el nuevo subtotal general
            nuevo_subtotal = 0
            for data in carrito.values():
                # Aseguramos que el precio se convierta a float y manejamos el caso por si falta la clave
                precio_item = float(data.get('precio', 0))
                cantidad_item = data.get('cantidad', 0)
                nuevo_subtotal += precio_item * cantidad_item
            
            # 3. Calcular el nuevo total final
            nuevo_total_final = nuevo_subtotal + costo_envio if nuevo_subtotal > 0 else 0.00
            
            return JsonResponse({
                'success': True,
                'message': mensaje,
                'producto_id': producto_id,
                # 🚨 DEVOLVEMOS LOS NUEVOS TOTALES AL JAVASCRIPT 🚨
                'new_subtotal': nuevo_subtotal,
                'new_total_final': nuevo_total_final 
            })
        
        # --- FALLBACK DE REDIRECCIÓN DURA (Si no es AJAX) ---
        messages.success(request, mensaje)
        return redirect('ver_carrito')
    
    # Si el producto no estaba en el carrito
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'message': 'El producto ya no estaba en el carrito.'})
    
    messages.warning(request, 'El producto que intentas eliminar no se encontró en el carrito.')
    return redirect('ver_carrito')