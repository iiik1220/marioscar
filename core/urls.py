from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('voiture/<int:car_id>/', views.car_detail, name='car_detail'),
    path('voiture/<int:car_id>/reserver/', views.choose_reservation_type, name='choose_reservation_type'),
    path('voiture/<int:car_id>/reservation-normale/', views.reservation_normal, name='reservation_normal'),
    path('voiture/<int:car_id>/reservation-complete/', views.reservation_complete, name='reservation_complete'),

    path('inscription/', views.signup_view, name='signup'),
    path('connexion/', views.login_view, name='login'),
    path('deconnexion/', views.logout_view, name='logout'),

    path('mes-reservations/', views.my_reservations, name='my_reservations'),
    path('annuler-reservation/<int:reservation_id>/', views.cancel_reservation, name='cancel_reservation'),
    path('checkout/<int:reservation_id>/', views.checkout, name='checkout'),
    path('payment-success-demo/<int:reservation_id>/', views.payment_success_demo, name='payment_success_demo'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('dashboard/modeles/', views.dashboard_car_models, name='dashboard_car_models'),
    path('dashboard/modeles/ajouter/', views.dashboard_car_model_add, name='dashboard_car_model_add'),
    path('dashboard/modeles/<int:car_id>/modifier/', views.dashboard_car_model_edit, name='dashboard_car_model_edit'),
    path('dashboard/modeles/<int:car_id>/supprimer/', views.dashboard_car_model_delete, name='dashboard_car_model_delete'),

    path('dashboard/unites/', views.dashboard_car_units, name='dashboard_car_units'),
    path('dashboard/unites/ajouter/', views.dashboard_car_unit_add, name='dashboard_car_unit_add'),
    path('dashboard/unites/<int:unit_id>/modifier/', views.dashboard_car_unit_edit, name='dashboard_car_unit_edit'),
    path('dashboard/unites/<int:unit_id>/supprimer/', views.dashboard_car_unit_delete, name='dashboard_car_unit_delete'),

    path('dashboard/clients/', views.dashboard_clients, name='dashboard_clients'),
    path('dashboard/clients/ajouter/', views.dashboard_client_add, name='dashboard_client_add'),
    path('dashboard/clients/<int:client_id>/modifier/', views.dashboard_client_edit, name='dashboard_client_edit'),
    path('dashboard/clients/<int:client_id>/supprimer/', views.dashboard_client_delete, name='dashboard_client_delete'),

    path('dashboard/reservations/', views.dashboard_reservations, name='dashboard_reservations'),
    path('dashboard/reservations/ajouter/', views.dashboard_reservation_add, name='dashboard_reservation_add'),
    path('dashboard/reservations/<int:reservation_id>/modifier/', views.dashboard_reservation_edit, name='dashboard_reservation_edit'),
    path('dashboard/reservations/<int:reservation_id>/supprimer/', views.dashboard_reservation_delete, name='dashboard_reservation_delete'),

    path('dashboard/finance/', views.dashboard_finance, name='dashboard_finance'),
    path('dashboard/finance/ajouter/<str:operation_type>/', views.finance_quick_add, name='finance_quick_add'),

    path('dashboard/entretiens/', views.dashboard_maintenances, name='dashboard_maintenances'),
    path('dashboard/entretiens/ajouter/', views.dashboard_maintenance_add, name='dashboard_maintenance_add'),
    path('dashboard/entretiens/<int:maintenance_id>/modifier/', views.dashboard_maintenance_edit, name='dashboard_maintenance_edit'),
    path('dashboard/entretiens/<int:maintenance_id>/supprimer/', views.dashboard_maintenance_delete, name='dashboard_maintenance_delete'),

    path('dashboard/accidents/', views.dashboard_accidents, name='dashboard_accidents'),
    path('dashboard/accidents/ajouter/', views.dashboard_accident_add, name='dashboard_accident_add'),
    path('dashboard/accidents/<int:accident_id>/modifier/', views.dashboard_accident_edit, name='dashboard_accident_edit'),
    path('dashboard/accidents/<int:accident_id>/supprimer/', views.dashboard_accident_delete, name='dashboard_accident_delete'),

    path('dashboard/pieces/', views.dashboard_parts, name='dashboard_parts'),
    path('dashboard/pieces/ajouter/', views.dashboard_part_add, name='dashboard_part_add'),
    path('paypal/create-order/<int:reservation_id>/', views.paypal_create_order, name='paypal_create_order'),
    path('paypal/capture-order/<int:reservation_id>/', views.paypal_capture_order, name='paypal_capture_order'),
    path('dashboard/pieces/<int:part_id>/modifier/', views.dashboard_part_edit, name='dashboard_part_edit'),
    path('dashboard/pieces/<int:part_id>/supprimer/', views.dashboard_part_delete, name='dashboard_part_delete'),
    path('dashboard/booking-control/', views.dashboard_booking_control, name='dashboard_booking_control'),
]